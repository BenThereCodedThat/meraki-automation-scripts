# Meraki Firewall Rule Loader

This script automates pushing L3 firewall rules to Cisco Meraki MX firewalls using an Excel spreadsheet.  
It supports modern policy object logic while maintaining full compatibility with current Meraki API limitations.

---

## ⚠️ Important SDK/API Limitation

> The Meraki Dashboard API **does not support directly referencing** policy objects or object groups in L3 firewall rules using the Python SDK (e.g., `objectId` or `OBJ(name)` syntax).  
> Even in the GUI, object references are resolved into standard CIDRs or FQDNs under the hood.

Therefore, this script:
- ✅ **Resolves policy objects and groups into CIDRs or FQDNs**
- ✅ **Expands object groups** into individual firewall rules for each value
- ❌ Does **not** attempt unsupported `objectId`/`objectType` push logic

---

## ✅ Features

- Supports single and dual MX networks
- Multithreaded rule pushing
- VLAN and CIDR source/destination support
- Full support for policy objects and object groups
- Policy object groups auto-expand into multiple rules
- Dry-run mode with rule diff comparison
- Validation and backup of existing rules before push
- Automatic correction of CIDR ↔ VLAN mismatches

---

## 📁 Project Files

| File                     | Purpose                                           |
|--------------------------|---------------------------------------------------|
| `meraki_fw_rule_loader.py` | Main script for applying rules                    |
| `meraki_fw_rules.xlsx`   | Excel spreadsheet with firewall rule definitions  |
| `*_fw_backup_*.json`     | Backup of current firewall rules (per firewall)   |

---

## 📦 Prerequisites

- Python 3.8+
- Install dependencies using:

```bash
pip install -r requirements.txt

---

## 🔐 API Key

You can provide your API key via:

- Command-line: `--api-key`
- Environment variable: `MERAKI_DASHBOARD_API_KEY`

---

## 📥 Excel Format

### Required Columns

| Rule # | Device       | Comment            | Policy | Protocol | Src Type | Src Value        | Src Port | Dst Type | Dst Value       | Dst Port |
|--------|--------------|--------------------|--------|----------|----------|------------------|----------|----------|-----------------|----------|
| 1      | GB-LAB-FW01  | Allow All Traffic  | allow  | any      | any      | any              | any      | any      | any             | any      |
| 2      | GB-LAB-FW01  | Allow DNS          | allow  | udp      | vlan     | Corp-Data        | any      | object   | Public-DNS      | 53       |
| 3      | GB-LAB-FW01  | Block Facebook     | deny   | any      | any      | any              | any      | fqdn     | *.facebook.com  | any      |

### Type Options

`Src Type` and `Dst Type` support:

- `cidr`
- `vlan`
- `fqdn`
- `object` (for policy objects or groups)
- `any`

---

## 🚀 Usage

### Basic

```bash
python meraki_fw_rule_loader.py
```

### With CLI Options

```bash
python meraki_fw_rule_loader.py --api-key YOUR_API_KEY --dry-run --max-threads 10
```

- `--dry-run`: Preview rules without applying them
- `--max-threads`: Parallel device processing (default: 5)

---

## 🔁 Object Group Expansion

When using an `object` or `group` like `Public-DNS`, which contains multiple CIDRs (e.g., `8.8.8.8`, `8.8.4.4`),  
the script expands this into multiple firewall rules:

```
Rule: Allow Corp to DNS → becomes:

  Rule 1: Src = Corp-Data, Dst = 8.8.8.8
  Rule 2: Src = Corp-Data, Dst = 8.8.4.4
```

This is necessary because **Meraki does not support multiple CIDRs in a single API-pushed rule**.

---

## 🛡️ Backup

Before any rule changes, the script saves the existing firewall rules to:

```
<device_name>_fw_backup_<timestamp>.json
```

This ensures rollback capability in case of error.

---

## 💡 Tips

- Make sure object/group names in Excel match those in the Meraki dashboard **exactly** (case-sensitive)
- Mixed FQDN/CIDR object groups are **skipped** for safety

---

## 📝 Example Dry Run Output

```text
[+] Processing GB-LAB-FW01

✅ VALID RULE:
{'srcCidr': '10.100.10.0/24', 'destCidr': '8.8.8.8', ...}

✅ VALID RULE:
{'srcCidr': '10.100.10.0/24', 'destCidr': '8.8.4.4', ...}

✅ VALID RULE:
{'srcCidr': 'any', 'destFqdn': '*.facebook.com', ...}

[✓] Dry run complete for GB-LAB-FW01
```

---

## 🧠 Known Limitations

- One CIDR/FQDN per rule — object groups are expanded to accommodate this
- Does not use Meraki beta object references (`objectId`) due to poor SDK support and known API issues

---
