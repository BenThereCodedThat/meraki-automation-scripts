import meraki
import pandas as pd
import os
import time
import argparse
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed


def parse_args():
    parser = argparse.ArgumentParser(description="Export Meraki wireless clients to Excel.")
    parser.add_argument('--api-key', help='Meraki API key. Falls back to MERAKI_DASHBOARD_API_KEY if not provided.')
    parser.add_argument('--org-id', required=True, help='Meraki Organization ID')
    parser.add_argument('--days', type=int, default=7, help='Days back to include (default: 7)')
    parser.add_argument('--output', help='Optional output Excel file path')
    return parser.parse_args()


def fetch_clients_for_network(dashboard, net, days_back):
    results = []
    net_id = net['id']
    net_name = net['name']

    if 'wireless' not in net.get('productTypes', []):
        return results

    print(f"[+] Processing: {net_name}")
    try:
        clients = dashboard.networks.getNetworkClients(
            net_id,
            timespan=days_back * 86400,
            perPage=1000,
            total_pages='all'
        )

        wireless_clients = 0
        for client in clients:
            if client.get('ssid'):
                wireless_clients += 1
                results.append({
                    'Network Name': net_name,
                    'Client Name': client.get('description') or '',
                    'MAC Address': client.get('mac'),
                    'IP Address': client.get('ip') or 'Unavailable',
                    'Device/OS Type': client.get('os') or 'Unknown',
                    'SSID': client.get('ssid')
                })

        print(f"[✓] {net_name}: {wireless_clients} wireless clients found.")

    except Exception as e:
        print(f"[!] Error with {net_name}: {e}")

    return results


def main():
    args = parse_args()
    api_key = args.api_key or os.getenv('MERAKI_DASHBOARD_API_KEY')
    if not api_key:
        print("❌ API key is required. Use --api-key or set MERAKI_DASHBOARD_API_KEY.")
        exit(1)

    org_id = args.org_id
    days_back = args.days
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = args.output or os.path.join(os.getcwd(), f'wireless_clients_{timestamp}.xlsx')

    dashboard = meraki.DashboardAPI(api_key, suppress_logging=True)

    start_time = time.perf_counter()
    all_data = []

    print("Fetching network list...")
    networks = dashboard.organizations.getOrganizationNetworks(org_id)
    print(f"Found {len(networks)} networks.")

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_network = {
            executor.submit(fetch_clients_for_network, dashboard, net, days_back): net['name']
            for net in networks
        }
        for future in as_completed(future_to_network):
            all_data.extend(future.result())

    df = pd.DataFrame(all_data)
    df.to_excel(output_file, index=False)

    print(f"\n✅ Done. {len(df)} wireless clients exported to:\n{output_file}")
    elapsed = time.perf_counter() - start_time
    print(f"⏱️ Elapsed time: {elapsed:.2f} seconds")


if __name__ == "__main__":
    main()
