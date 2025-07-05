# Same imports as before
import argparse, os, json, pandas as pd, meraki, requests
from collections import defaultdict
from pathlib import Path
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pprint

parser = argparse.ArgumentParser(description='Push Meraki firewall rules from Excel.')
parser.add_argument('--api-key', help='Meraki API Key (or use MERAKI_DASHBOARD_API_KEY)')
parser.add_argument('--excel-file', default='meraki_fw_rules.xlsx')
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--max-threads', type=int, default=5)
args = parser.parse_args()

start_time = time.time()
API_KEY = args.api_key or os.getenv("MERAKI_DASHBOARD_API_KEY")
if not API_KEY:
    raise ValueError("API key is required.")

SCRIPT_DIR = Path(__file__).resolve().parent
EXCEL_PATH = SCRIPT_DIR / args.excel_file
if not EXCEL_PATH.exists():
    raise FileNotFoundError(f"Excel file '{EXCEL_PATH.name}' not found in: {SCRIPT_DIR}")

print(f"Using Excel file: {EXCEL_PATH.name}")
dashboard = meraki.DashboardAPI(API_KEY, suppress_logging=True)
df = pd.read_excel(EXCEL_PATH)

device_rule_map = defaultdict(list)
for _, row in df.iterrows():
    device_ref = str(row['Device']).strip()
    device_rule_map[device_ref].append(row)

def get_all_devices_by_org():
    orgs = dashboard.organizations.getOrganizations()
    all_devs = []
    for org in orgs:
        try:
            devs = dashboard.organizations.getOrganizationDevices(org['id'])
            for d in devs:
                d['orgId'] = org['id']
            all_devs.extend(devs)
        except:
            continue
    return all_devs

def get_device_info_map():
    device_map = {}
    for d in get_all_devices_by_org():
        if d['model'].startswith('MX'):
            if 'serial' in d:
                device_map[d['serial'].upper()] = d
            if d.get('name'):
                device_map[d['name'].strip().upper()] = d
    return device_map

def is_dual_mx(network_id):
    try:
        devs = dashboard.networks.getNetworkDevices(network_id)
        return len([d for d in devs if d['model'].startswith('MX')]) > 1
    except:
        return False

def get_vlan_objects(network_id):
    try:
        vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
        return {v['name']: v['subnet'] for v in vlans}
    except:
        return {}

def get_object_value_map(api_key, org_id):
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    base_url = f"https://api.meraki.com/api/v1/organizations/{org_id}"
    object_values = {}
    object_lookup = {}

    try:
        obj_resp = requests.get(f"{base_url}/policyObjects", headers=headers)
        objects = obj_resp.json() if obj_resp.ok else []

        for obj in objects:
            if obj.get("cidr"):
                object_values[obj['name']] = obj["cidr"]
                object_lookup[obj['name']] = "cidr"
            elif obj.get("fqdn"):
                object_values[obj['name']] = obj["fqdn"]
                object_lookup[obj['name']] = "fqdn"

        group_resp = requests.get(f"{base_url}/policyObjects/groups", headers=headers)
        groups = group_resp.json() if group_resp.ok else []

        obj_map = {o['id']: o for o in objects}

        for group in groups:
            cidrs, fqdns = [], []
            for obj_id in group.get("objectIds", []):
                obj = obj_map.get(obj_id)
                if not obj:
                    continue
                if obj.get("cidr"):
                    cidrs.append(obj["cidr"])
                elif obj.get("fqdn"):
                    fqdns.append(obj["fqdn"])
            if cidrs and fqdns:
                print(f"  ⚠️ Skipping mixed group '{group['name']}'")
                continue
            if cidrs:
                object_values[group['name']] = cidrs
                object_lookup[group['name']] = "cidr"
            elif fqdns:
                object_values[group['name']] = fqdns
                object_lookup[group['name']] = "fqdn"

    except Exception as e:
        print(f"❌ Failed fetching policy objects/groups: {e}")
    return object_values, object_lookup

def expand_rule(row, vlan_map, use_vlan_objects, object_values, object_lookup):
    rules = []
    base = {
        "comment": row["Comment"],
        "policy": str(row["Policy"]).lower(),
        "protocol": str(row["Protocol"]).lower(),
        "srcPort": str(row["Src Port"]),
        "destPort": str(row["Dst Port"])
    }

    src_type = str(row["Src Type"]).lower()
    src_val = str(row["Src Value"]).strip() if pd.notna(row["Src Value"]) else ""
    dst_type = str(row["Dst Type"]).lower()
    dst_val = str(row["Dst Value"]).strip() if pd.notna(row["Dst Value"]) else ""

    src_cidrs = []
    dst_targets = []

    # Source logic
    if src_type == "vlan" and use_vlan_objects:
        src_cidrs = [vlan_map.get(src_val, "any")]
    elif src_type == "cidr":
        src_cidrs = [src_val]
    elif src_type == "object":
        if src_val not in object_values or object_lookup[src_val] != "cidr":
            print(f"  ❌ Invalid or FQDN source object: {src_val}")
            return [{"invalid": True, **base}]
        val = object_values[src_val]
        src_cidrs = val if isinstance(val, list) else [val]
    elif src_type == "any":
        src_cidrs = ["any"]
    else:
        src_cidrs = [src_val]

    # Dest logic
    if dst_type == "vlan" and use_vlan_objects:
        dst_targets = [{"destCidr": vlan_map.get(dst_val, "any")}]
    elif dst_type == "cidr":
        dst_targets = [{"destCidr": dst_val}]
    elif dst_type == "object":
        if dst_val not in object_values:
            print(f"  ❌ Invalid destination object: {dst_val}")
            return [{"invalid": True, **base}]
        val = object_values[dst_val]
        if object_lookup[dst_val] == "cidr":
            items = val if isinstance(val, list) else [val]
            dst_targets = [{"destCidr": cidr} for cidr in items]
        elif object_lookup[dst_val] == "fqdn":
            items = val if isinstance(val, list) else [val]
            dst_targets = [{"destFqdn": fqdn, "destCidr": "any"} for fqdn in items]
    elif dst_type == "fqdn":
        dst_targets = [{"destFqdn": dst_val, "destCidr": "any"}]
    elif dst_type == "any":
        dst_targets = [{"destCidr": "any"}]

    # Build expanded rule set
    for src in src_cidrs:
        for dst in dst_targets:
            rule = base.copy()
            rule["srcCidr"] = src
            rule.update(dst)
            rules.append(rule)

    return rules

def compare_rules(old, new):
    print("\n🔍 DRY RUN COMPARISON:")
    norm = lambda r: json.dumps(r, sort_keys=True)
    old_set = set(map(norm, old))
    new_set = set(map(norm, new))

    for r in new_set - old_set:
        print("\n🟢 NEW RULE:\n", pprint.pformat(json.loads(r)))
    for r in old_set - new_set:
        print("\n🔴 REMOVED RULE:\n", pprint.pformat(json.loads(r)))

def process_firewall(device_ref, ruleset, dashboard, device_map, script_dir, dry_run, api_key):
    ref = device_ref.upper()
    if ref not in device_map:
        return f"[!] Device '{device_ref}' not found."

    device = device_map[ref]
    net_id = device["networkId"]
    org_id = device["orgId"]
    name = device.get("name", device["serial"])
    dual = is_dual_mx(net_id)
    vlans = get_vlan_objects(net_id) if not dual else {}
    use_vlans = not dual
    object_values, object_lookup = get_object_value_map(api_key, org_id)

    print(f"\n[+] Processing {name} (Dual MX: {dual})")
    rules = []
    invalid = False

    if isinstance(ruleset, list) and ruleset and 'Rule #' in ruleset[0]:
        ruleset.sort(key=lambda r: r['Rule #'])

    for row in ruleset:
        expanded = expand_rule(row, vlans, use_vlans, object_values, object_lookup)
        for rule in expanded:
            if rule.get("invalid"):
                print("\n❌ INVALID RULE:\n", pprint.pformat(rule))
                invalid = True
            else:
                print("\n✅ VALID RULE:\n", pprint.pformat(rule))
            rules.append(rule)

    if invalid:
        return "[!] Skipped due to invalid rules."

    existing = dashboard.appliance.getNetworkApplianceFirewallL3FirewallRules(net_id)
    backup = existing.get("rules", [])
    if dry_run:
        compare_rules(backup, rules)
        return f"[✓] Dry run complete for {name}"
    else:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        bkp = script_dir / f"{name}_fw_backup_{ts}.json"
        with open(bkp, "w") as f:
            json.dump(backup, f, indent=2)
        dashboard.appliance.updateNetworkApplianceFirewallL3FirewallRules(net_id, rules=rules)
        return f"[✓] Pushed {len(rules)} rules to {name}"

# === THREAD EXECUTION ===
device_map = get_device_info_map()
with ThreadPoolExecutor(max_workers=args.max_threads) as executor:
    futures = [executor.submit(
        process_firewall, ref, ruleset, dashboard, device_map, SCRIPT_DIR, args.dry_run, API_KEY
    ) for ref, ruleset in device_rule_map.items()]
    for f in as_completed(futures):
        print(f.result())

print(f"\n🕒 Script finished in {time.time() - start_time:.2f} seconds.")
