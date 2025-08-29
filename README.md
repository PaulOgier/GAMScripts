# Google Workspace & GAM Automation Scripts 🚀

Welcome! This repository is a collection of powerful and easy-to-use Python scripts designed to supercharge your **Google Workspace administration** by leveraging the incredible capabilities of **GAM7 (Google Apps Manager)**.

Whether you're looking to perform **bulk operations**, process large CSV reports, or automate repetitive tasks, these scripts are here to save you time and prevent headaches.

---

## ✨ What's Inside?

This collection helps you automate tedious Google Workspace tasks that are difficult or time-consuming to do manually. Our goal is to provide practical solutions for real-world administrative challenges.

* **Automate User Management**: Bulk update user attributes, process new hires, and manage offboarding.
* **Process Large Reports**: Split, filter, and group massive CSV exports from GAM or the Admin Console.
* **Manage Google Calendar & Drive**: Perform bulk operations on calendar events or Drive files across your organization.
* **Streamline Workflows**: Chain commands and logic together for complex, multi-step administrative processes.



---

## 🔧 Prerequisites

Before you begin, make sure you have the following installed and configured:

1.  **Python 3**: These scripts are written for Python 3.6 or newer. You can check your version with `python3 --version`.
2.  **GAMADV-XTD3 or GAM7**: The latest and most powerful version of GAM. Ensure it's properly installed, configured, and authorized to access your Google Workspace domain. You can find it here: [GAMADV-XTD3 GitHub Repository](https://github.com/taers232c/GAMADV-XTD3) or [GAM7 GitHub Repository](https://github.com/GAM-team/GAM/wiki).

---

## 📚 Scripts Library

Here is a breakdown of the available scripts. Each script is designed to solve a specific problem.

### **1. Split Calendar CSV Events \ CSV File Splitter (`split_by_size.py`)**

* **Description**: Splits a single, massive CSV file into smaller, more manageable chunks based on a specified file size (e.g., 5 MB).
* **Best For**: Processing huge GAM reports that are too large to open in Google Sheets or Microsoft Excel.
* **Usage**:
    ```bash
    python3 split_by_size.py <input_file.csv> [max_size_in_mb]
    ```
    * `<input_file.csv>`: The path to the large CSV you want to split.
    * `[max_size_in_mb]`: (Optional) The maximum file size for each chunk. Defaults to 5.

<br>

### **2. Split Calendar CSV Events \ User Event Exporter (`filter_and_split.py`)**

* **Description**: Filters a master CSV of calendar events for multiple users and creates a separate CSV file for each user containing only their events from a recent period.
* **Best For**: Auditing recent user activity or creating individual calendar reports for compliance or archival purposes.
* **Usage**:
    ```bash
    python3 filter_and_split.py <input_file.csv> <days_ago>
    ```
    * `<input_file.csv>`: The master CSV containing events for all users.
    * `<days_ago>`: The number of days back from today to include events for (e.g., `30`).

<br>

### **3. Split Calendar CSV Events \ Single User CSV Creator (`split_csv.py`)**

* **Description**: Takes a CSV file with multiple users and creates a new, individual CSV file for each user listed.
* **Best For**: Creating individual data files for mail merges, or preparing data for other scripts that need to run on a per-user basis.
* **Usage**:
    ```bash
    python3 split_csv.py <input_file.csv>
    ```
    * `<input_file.csv>`: The CSV file containing a 'primaryEmail' column.

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📧 Contact

Paul Ogier / OSH.co.za and Taming.Tech - paul@osh.co.za https://osh.co.za paul@taming.tech https://taming.tech


