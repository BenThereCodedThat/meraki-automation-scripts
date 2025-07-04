# Meraki Switch Port Bulk Updater

This Python script allows you to **bulk update Cisco Meraki switch ports** using an Excel spreadsheet.  
It supports updating port descriptions, VLANs, trunk/access types, and more — with smart change detection to avoid unnecessary API calls.

---

## ✅ Features

- Bulk updates Meraki switch ports from an Excel file
- Supports:
  - Port **descriptions**
  - Port **type** (`access` or `trunk`)
  - **VLAN**, **voice VLAN**, **native VLAN**, **allowed VLANs**
- Skips ports if no change is needed (based on live API comparison)
- Multithreaded: updates multiple switches in parallel
- Accepts Meraki API key via:
  - `--api-key` CLI argument, or
  - `MERAKI_DASHBOARD_API_KEY` environment variable
- Displays total execution time

---

## 📦 Requirements

- Python 3.8+
- Meraki Dashboard API key (with org/network write access)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 📊 Excel Format

Create a file named `port_descriptions.xlsx` in the same directory as the script.

| Switch Serial | Port Number | Description     | Type   | VLAN | Voice VLAN | Native VLAN | Allowed VLANs |
|---------------|-------------|------------------|--------|------|------------|-------------|----------------|
| Q2QN-ABCD-1234| 1           | Core Uplink      | trunk  |      |            | 10          | all            |
| Q2QN-ABCD-1234| 2           | Office Printer   | access | 20   | 130        |             |                |

> Any empty field will be ignored and not changed.  
> If all configurable fields are empty, the port is skipped.

---

## 🚀 Usage

### Option 1: Pass API key via CLI

```bash
python update_meraki_ports.py --api-key your_api_key_here
```

### Option 2: Use an environment variable

```bash
export MERAKI_DASHBOARD_API_KEY=your_api_key_here
python update_meraki_ports.py
```

For Windows CMD:

```cmd
set MERAKI_DASHBOARD_API_KEY=your_api_key_here
python update_meraki_ports.py
```

---

## 🔎 Sample Output

```
✅ Updated port 2 on Q2QN-ABCD-1234
⏭️  Skipping port 3 on Q2QN-ABCD-1234 (no changes).
⏱️ Script completed in 0 min 9 sec.
```

---

## ⚙️ Notes

- Adjust `MAX_THREADS` in the script to match your environment and Meraki API rate limits.
- The script uses per-switch threading for efficient execution across large environments.
- It uses `requests.Session()` to reuse connections and speed up API access.

---

## 📄 License

MIT License

---
