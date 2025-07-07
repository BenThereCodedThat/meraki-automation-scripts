# Meraki Wireless Client Exporter

**Meraki Wireless Client Exporter** is a multithreaded Python script that queries all networks in a Meraki organization and exports data on **wireless clients** to an Excel spreadsheet.

---

## 🚀 Features

- Exports **wireless client** information (name, MAC, IP, OS, SSID)
- Automatically filters out non-wireless networks
- Supports configurable time range (`--days`)
- Multithreaded for fast performance across large orgs
- Output saved in timestamped `.xlsx` format
- API key can be passed via CLI or environment variable (`MERAKI_DASHBOARD_API_KEY`)

---

## 📦 Requirements

- Python 3.7+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

---

## 🛠️ Usage

```bash
python meraki_wireless_client_exporter.py --org-id <ORG_ID> [--api-key <API_KEY>] [--days <DAYS>] [--output <FILE>]
```

### Arguments

| Argument       | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `--org-id`     | **(Required)** Meraki Organization ID                                       |
| `--api-key`    | Meraki Dashboard API key. If omitted, the script uses `MERAKI_DASHBOARD_API_KEY` from your environment. |
| `--days`       | Number of days back to include (default: `7`)                               |
| `--output`     | Optional path for the output `.xlsx` file. If omitted, defaults to `./wireless_clients_<timestamp>.xlsx` |

### Example

```bash
export MERAKI_DASHBOARD_API_KEY=abc1234567890
python meraki_wireless_client_exporter.py --org-id 123456789 --days 3
```

---

## 📄 Output

The script generates an Excel file with the following columns:

- `Network Name`
- `Client Name`
- `MAC Address`
- `IP Address`
- `Device/OS Type`
- `SSID`

Each row represents a wireless client seen within the selected time window across any wireless-enabled Meraki network.

---

## 📌 Notes

- This script only includes **wireless clients** (those with an associated SSID).
- Networks that do not have wireless product types are skipped automatically.

---

## 🧾 License

This project is licensed under the MIT License.
