# Smartlead Weekly Mailbox Analytics

A production-ready Python backend and API integration service that connects with the official Smartlead API to generate granular, mailbox-level email delivery and bounce rate reports across clients and campaigns.

---

## 1. Project Overview

In outbound email infrastructure, agencies and businesses manage multiple clients, each running several cold email campaigns across rotating sending mailboxes (email accounts). High deliverability demands monitoring delivery health at the **individual mailbox level**, rather than just broad campaign totals.

**Smartlead Weekly Mailbox Analytics** provides automated weekly reporting answering the fundamental deliverability question:
> *"For every client, how many emails did each mailbox send last week, how many bounced, and what was the bounce rate?"*

### Key Features
- **Client & Mailbox Hierarchy**: Correctly aggregates across `Client -> Campaigns -> Email Accounts (Mailboxes)`.
- **Duplicate Prevention**: Dedupes mailboxes assigned to multiple campaigns without double-counting sent or bounced statistics.
- **Calendar-Week Logic**: Calculates standard previous calendar week (Monday 00:00:00 through Sunday 23:59:59) and supports custom date intervals.
- **Data Integrity & Validation**: Strictly enforces `sent >= 0`, `bounced >= 0`, and validates upstream provider anomalies.
- **Zero-Guess Attribution**: Adheres to strict data accuracy standards; if a multi-mailbox campaign lacks mailbox-level breakdown, it is transparently noted rather than guessed.
- **Real-Time Webhook Support**: Ingests official Smartlead `EMAIL_SENT` and `EMAIL_BOUNCE` webhooks for 100% exact per-mailbox event attribution.
- **Multi-Sheet Excel Reports**: Generates professional spreadsheets using `openpyxl` with frozen headers, auto-filters, percentage formatting, and auto-sized columns.
- **Interactive Web Dashboard**: Built-in, responsive HTML5 dashboard with KPI summary cards and client-to-mailbox drill-down.
- **Automated APScheduler**: Built-in cron scheduler running weekly reports every Monday morning.
- **Security-First**: Zero API key leakage. Log sanitization scrubbers filter secrets from all logs and API responses.
- **Windows-Native & Cross-Platform**: No Docker or Redis required.

---

## 2. Architecture

```
                                  +-----------------------------+
                                  |      Smartlead REST API     |
                                  | (server.smartlead.ai/api/v1)|
                                  +--------------+--------------+
                                                 |
                                     (HTTP Basic Auth / ?api_key)
                                                 |
                                                 v
+------------------------+           +--------------------------+
| Smartlead Webhooks     |           |   SmartleadApiClient     |
| (EMAIL_SENT,           |           | - Concurrency Semaphore  |
|  EMAIL_BOUNCE)         |           | - Exp. Backoff & 429     |
+-----------+------------+           +-------------+------------+
            |                                      |
            v                                      v
+-----------+------------+           +-------------+------------+
| /api/webhooks/smartlead|           |   Services Layer         |
| Ingestion & Event DB   |           | - ClientService          |
+-----------+------------+           | - CampaignService        |
            |                        | - MailboxService         |
            |                        | - AnalyticsService       |
            +------------+-----------+                          |
                         |                                      |
                         v                                      v
            +------------+--------------------------------------+
            |               AggregationService                  |
            | - Mailbox Canonical Key (ID / Normalized Email)   |
            | - Cross-Campaign Non-Duplicating Summation        |
            | - Accurate Bounce Rate Calculation                |
            +---------------------------+-----------------------+
                                        |
                         +--------------+--------------+
                         |                             |
                         v                             v
            +------------+-----------+   +-------------+------------+
            |   Database Storage     |   |   Report & Excel Service |
            | (PostgreSQL / SQLite)  |   | (openpyxl 3-Sheet Report)|
            +------------+-----------+   +-------------+------------+
                         |                             |
                         v                             v
            +------------------------------------------+------------+
            |      FastAPI Server & Built-in Web Dashboard           |
            |  - GET /api/reports/weekly                            |
            |  - GET /api/reports/weekly/export                     |
            |  - POST /api/reports/generate                         |
            |  - Interactive Web Dashboard at http://localhost:8000  |
            +-------------------------------------------------------+
```

---

## 3. Smartlead API Setup

1. Log in to your Smartlead account at [app.smartlead.ai](https://app.smartlead.ai).
2. Navigate to **Settings** (click your profile icon) -> **API Key**.
3. Click **Generate New API Key**.
4. Copy the API key immediately.

---

## 4. API Key Setup

Store your Smartlead API key in the `.env` file in the project root directory.

```bash
SMARTLEAD_API_KEY=your_actual_smartlead_api_key_here
```

**Security Guarantees:**
- Never hardcode the API key in code files.
- `.env` is explicitly ignored in `.gitignore`.
- All console and file loggers pass through `SensitiveDataFilter` to redact API keys, tokens, and authorization parameters.

---

## 5. .env Configuration

Create your `.env` file by copying `.env.example`:

```bash
copy .env.example .env
```

Configuration variables:

```ini
# Smartlead API Credentials
SMARTLEAD_API_KEY=your_api_key_here
API_BASE_URL=https://server.smartlead.ai/api/v1
SMARTLEAD_MAX_CONCURRENCY=5

# Database Connection
# Default SQLite for zero-setup local Windows execution:
DATABASE_URL=sqlite:///./smartlead_analytics.db
# Or PostgreSQL for production:
# DATABASE_URL=postgresql://postgres:password@localhost:5432/smartlead_db

# Application Settings
DRY_RUN=true
LOG_LEVEL=INFO

# Scheduled Weekly Report Execution
REPORT_DAY=MONDAY
REPORT_HOUR=09
REPORT_MINUTE=00
```

---

## 6. PostgreSQL Setup (Optional)

The application supports both PostgreSQL and SQLite. For instant local development on Windows, SQLite works immediately without any external services.

For PostgreSQL in production:
1. Create a database:
   ```sql
   CREATE DATABASE smartlead_db;
   ```
2. Update `.env`:
   ```ini
   DATABASE_URL=postgresql://user:password@localhost:5432/smartlead_db
   ```
3. Tables are created automatically when the application starts via SQLAlchemy.

---

## 7. Installation

### 1. Create Virtual Environment
```bash
python -m venv venv
```

### 2. Activate Virtual Environment (Windows)
```cmd
venv\Scripts\activate
```
*(On Linux/macOS: `source venv/bin/activate`)*

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 8. Running the Server

Start the FastAPI application and dashboard with auto-reload:

```bash
uvicorn app.main:app --reload
```
or via the runner script:
```bash
python run.py --serve --reload
```

Once running:
- **Web Dashboard**: Open [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Documentation (Swagger)**: Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc**: Open [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 9. Testing Smartlead Connection

Verify your credentials and API connectivity safely:

```bash
python run.py --test-smartlead
```

Output example:
```
==================================================
SMARTLEAD API CONNECTION TEST
==================================================
API Base URL: https://server.smartlead.ai/api/v1
API Key:      sk***123
Dry Run Mode: True
Sending safe verification request...

Result:
Status:  success
Message: Successfully connected to Smartlead API. Accessible campaigns count: 8
Accessible Campaigns: 8
==================================================
```

---

## 10. Generating Weekly Report

### Generate Previous Calendar Week Report (CLI)
```bash
python run.py --generate-weekly-report
```

### Generate Custom Date Range Report (CLI)
```bash
python run.py --generate-report --start-date 2026-09-21 --end-date 2026-09-27
```

Report files are exported to the `exports/` folder:
`exports/weekly_mailbox_report_2026-09-21_to_2026-09-27.xlsx`

---

## 11. Excel Report Structure

The generated Excel workbook contains three professionally formatted sheets:

### Sheet 1: `Weekly Mailbox Report`
Lists each mailbox under each client:
- **Columns**: `Client Name`, `Client ID`, `Mailbox`, `Mailbox ID`, `Sent`, `Bounced`, `Bounce Rate`, `Period Start`, `Period End`.
- **Formatting**: Frozen header row, auto-filters enabled, percentage format (`0.00%`), number separators (`#,##0`), and auto-fitted columns.

### Sheet 2: `Client Summary`
Aggregated overview per client:
- **Columns**: `Client Name`, `Total Mailboxes`, `Total Sent`, `Total Bounced`, `Overall Bounce Rate`.
- **Formatting**: Frozen headers, auto-filters, bold styled header cells.

### Sheet 3: `Report Metadata`
Audit trail and run parameters:
- **Fields**: `Generated At`, `Period Start`, `Period End`, `API Source`, `Number of Clients`, `Number of Mailboxes`, `Total Sent`, `Total Bounced`, `Overall Bounce Rate`.

---

## 12. Date Calculation Logic

The report defaults strictly to the **previous calendar week** (Monday 00:00:00 through Sunday 23:59:59).

### Algorithm
```python
weekday = reference_date.weekday() # Monday = 0, Sunday = 6
current_week_monday = reference_date - timedelta(days=weekday)
previous_week_sunday = current_week_monday - timedelta(days=1)
previous_week_monday = previous_week_sunday - timedelta(days=6)
```

Example:
- If today is **Wednesday, September 30, 2026**:
  - Current Monday: September 28, 2026
  - Previous Sunday: September 27, 2026
  - Previous Monday: September 21, 2026
  - **Covered Date Range**: Monday September 21, 2026 to Sunday September 27, 2026.

---

## 13. Mailbox Aggregation Logic

When a single mailbox is attached to multiple campaigns, its statistics must be merged accurately without duplicate rows:

### Example:
- **Mailbox**: `sales@company.com` (ID `987`)
- **Campaign A**: Sent = 300, Bounced = 5
- **Campaign B**: Sent = 200, Bounced = 3

### Aggregated Result:
- `sales@company.com` (ID `987`):
  - **Sent**: 500
  - **Bounced**: 8
  - **Bounce Rate**: `(8 / 500) * 100 = 1.60%`

### Bounce Rate Formula
$$\text{Bounce Rate} = \frac{\text{Bounced}}{\text{Sent}} \times 100$$
- If $\text{Sent} = 0$, $\text{Bounce Rate} = 0.00\%$.
- Rounded to 2 decimal places.

---

## 14. Duplicate Prevention

1. **Unique Mailbox Key Resolution**:
   - Primary: `smartlead_email_account_id`
   - Fallback: `normalize_email(email)` (lowercased, stripped of leading/trailing spaces).
2. **Duplicate Campaign Pair Elimination**:
   - The aggregation service tracks `(campaign_id, mailbox_key)` to discard duplicate pairings.
3. **Database Constraints**:
   - `campaigns.smartlead_campaign_id`: `UNIQUE`
   - `mailboxes.smartlead_email_account_id`: `UNIQUE`
   - `campaign_mailboxes (campaign_id, mailbox_id)`: `UNIQUE`
   - `mailbox_stats (mailbox_id, period_start, period_end)`: `UNIQUE`

---

## 15. Rate Limiting & Concurrency

- Requests to Smartlead are bounded using `asyncio.Semaphore(SMARTLEAD_MAX_CONCURRENCY)` (default `5`).
- Complies with Smartlead's rate limits.
- On HTTP `429 Too Many Requests`:
  - Parses `Retry-After` header.
  - Automatically sleeps and retries using exponential backoff ($1.0\text{s} \to 2.0\text{s} \to 4.0\text{s}$).

---

## 16. Error Handling

- **401 / 403 (Authentication Error)**: Fails fast, logs an error without retrying indefinitely, and redacts credentials.
- **404 (Not Found)**: Gracefully handles missing sub-accounts or campaigns.
- **429 (Rate Limit)**: Exponential backoff with `Retry-After` header respect.
- **500+ (Server Errors)**: Retries up to 3 times before raising `SmartleadServerError`.
- **Network Timeouts**: Handles connection and read timeouts with retry backoff.
- **Data Validation**:
  - Validates `sent >= 0` and `bounced >= 0`.
  - Warns if `bounced > sent` due to upstream anomalies.

---

## 17. On-Demand Reporting (Instant Check)

Background scheduler cron jobs have been completely disabled/removed in favor of **100% on-demand reporting**. You can fetch and check data instantly at any moment:

1. **Via Web Dashboard**:
   - Open `http://127.0.0.1:8000`
   - Select any date range (or leave blank for previous calendar week)
   - Click **Generate Report** to immediately pull live data from Smartlead and display the results.
   - Click **Download Excel** to download the spreadsheet instantly.

2. **Via CLI Runner**:
   - Immediate previous week report:
     ```bash
     python run.py --generate-weekly-report
     ```
   - Immediate custom date range report:
     ```bash
     python run.py --generate-report --start-date 2026-09-21 --end-date 2026-09-27
     ```

3. **Via REST API**:
   - `GET /api/reports/weekly` (or `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`)
   - `POST /api/reports/generate`

---

## 18. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Web Dashboard |
| `GET` | `/health` | Service health status |
| `GET` | `/api/clients/` | List all synced clients |
| `GET` | `/api/campaigns/` | List campaigns (optional `?client_id=`) |
| `GET` | `/api/mailboxes/` | List synced mailboxes |
| `GET` | `/api/analytics/campaign/{id}` | Date-range metrics for a campaign |
| `GET` | `/api/reports/weekly` | Fetch weekly report JSON (`?start_date=&end_date=`) |
| `GET` | `/api/reports/weekly/export` | Download Excel report spreadsheet |
| `POST` | `/api/reports/generate` | Trigger on-demand report generation |
| `POST` | `/api/webhooks/smartlead` | Ingest live `EMAIL_SENT` / `EMAIL_BOUNCE` events |

---

## 19. Security

- **Environment-Only Secrets**: The API key is stored only in `.env`.
- **Zero Secret Ingestion in VCS**: `.env` is tracked in `.gitignore`.
- **Log Sanitization**: `SensitiveDataFilter` scrubs all logs:
  - Masks query parameters `?api_key=...`
  - Masks headers `Authorization: Bearer ...`
  - Masks JSON secret keys
- **API Defense**: Endpoints never return the API key.
- **Client Privacy**: Frontend communicates exclusively with your backend, never directly with Smartlead.

---

## 20. Smartlead API Limitations & Attribution Architecture

### The Architectural Distinction
Smartlead provides the following REST endpoints:
- `GET /campaigns/{campaign_id}/analytics-by-date`: Returns aggregate campaign counts (`sent_count`, `bounce_count`) broken down by date, but **not** by individual email account.
- `GET /campaigns/{campaign_id}/email-accounts`: Returns the list of email accounts attached to a campaign.

### Accuracy Rule
According to strict data accuracy requirements:
- **Campaigns with 1 Mailbox**: 100% of sent and bounced counts are directly attributed to that single mailbox with exact certainty.
- **Campaigns with Multiple Mailboxes**: Smartlead rotates outgoing emails across the accounts. **We do not guess or divide numbers arbitrarily.**
  - If webhooks are enabled, exact events are counted.
  - If webhooks are not present for that period, the status is explicitly documented as `API Limitation (Multi-Mailbox)` with zero sent/bounced rather than guessing.

### Safest Real-Time Architecture: Webhooks
Smartlead's webhook subsystem emits:
- `EMAIL_SENT`
- `EMAIL_BOUNCE` (or `EMAIL_BOUNCED`)

These webhooks include `email_account_id` and `timestamp`. The included `/api/webhooks/smartlead` endpoint stores these events in `mailbox_events`. When generating weekly reports, the system automatically uses these verified events for 100% exact multi-mailbox reporting.

---

## 21. Troubleshooting

### 1. `Smartlead API authentication failure (HTTP 401)`
- Ensure `SMARTLEAD_API_KEY` in `.env` is correct.
- Verify your API key has permissions in [app.smartlead.ai](https://app.smartlead.ai).
- Test connection via `python run.py --test-smartlead`.

### 2. `Rate limit hit (429)`
- Lower `SMARTLEAD_MAX_CONCURRENCY` in `.env` (e.g., set to `2` or `3`).
- The client automatically retries with backoff.

### 3. Missing Sub-Accounts
- If your Smartlead account is a standard single-user account (not an agency sub-account plan), the system automatically creates and maps to a `"Primary Workspace"` client.

### 4. Running Tests
Run the complete test suite:
```bash
python -m pytest -v
```
All 32 test cases run completely offline without requiring a real Smartlead API key.
