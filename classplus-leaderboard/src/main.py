import asyncio
import httpx
from fastapi import FastAPI, BackgroundTasks
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta

app = FastAPI()


SERVICE_ACCOUNT_FILE = "service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = ""     # Replace with your sheet ID
SHEET_NAME = ""                      # Replace with your sheet name
COUPON_API_URL = "https://api.classplusapp.com/cams/graph-api"


def get_sheet_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

sheet_service = get_sheet_service()
sheet = sheet_service.spreadsheets()

def read_sheet_range(range_name: str):
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SHEET_NAME}!{range_name}").execute()
    return result.get("values", [])

def update_sheet_range(range_name: str, values):
    body = {"values": values}
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{range_name}",
        valueInputOption="RAW",
        body=body
    ).execute()

def clear_sheet_range(range_name: str):
    sheet.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{range_name}"
    ).execute()

def format_date_to_ddmmyyyy(date_obj: datetime) -> str:
    return date_obj.strftime("%d/%m/%Y")


async def fetch_coupon_details_async(token: str, code: str):
    """Fetch coupon details (ID and redeem count) for a given coupon code."""
    query = """
    query ($token: String!, $search: String!) {
      withAuth(token: $token) {
        user {
          tutor {
            coupons(limit: 1, couponType: ALL, offset: 0, search: $search) {
              id
              name
              code
              redeemCount(state: SETTLED)
            }
          }
        }
      }
    }
    """
    variables = {"token": token, "search": code}
    payload = {"query": query, "variables": variables}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(COUPON_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        coupon = data.get("data", {}) \
                     .get("withAuth", {}) \
                     .get("user", {}) \
                     .get("tutor", {}) \
                     .get("coupons", [None])[0]
        if coupon:
            return [coupon.get("id", "Not Found"), coupon.get("redeemCount", "Not Available")]
        else:
            return ["Not Found", "Not Available"]

async def fetch_coupon_data_async(token: str, couponId: str, limit: int, offset: int):
    """Fetch detailed coupon data (including redeems) for a given coupon ID."""
    query = """
      query ($token: String!, $couponId: String, $limit: Int, $offset: Int) {
        withAuth(token: $token) {
          user {
            coupon(id:$couponId) {
              id
              code
              name
              redeemCount(state: SETTLED)
              redeems(limit: $limit, offset: $offset, state: SETTLED) {
                id
                courses { id name }
                user { id name imageUrl mobile }
                redeemedAt
                settledAt
                initialAmount
                discountAmount
                discountedAmount
              }
            }
          }
        }
      }
    """
    variables = {"token": token, "couponId": couponId, "limit": limit, "offset": offset}
    payload = {"query": query, "variables": variables}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.post(COUPON_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def find_row_with_yesterdays_date(startDate: datetime) -> int:
    try:
        days = int(read_sheet_range("R5")[0][0])
    except Exception:
        days = 1
    colA = read_sheet_range("A:A")
    for i in range(days):
        test_date = startDate + timedelta(days=i)
        formatted_date = format_date_to_ddmmyyyy(test_date)
        for idx, row in enumerate(colA, start=1):
            if row and row[0] == formatted_date:
                return idx
    colC = read_sheet_range("C:C")
    last_filled = len(colC)
    return last_filled + 2 if last_filled > 1 else 2

async def process_coupon_updates():

    clear_sheet_range("O2:P1000")
    token_val = read_sheet_range("R2")[0][0]
    coupon_codes = [row[0] for row in read_sheet_range("N2:N1000") if row]
    tasks = [fetch_coupon_details_async(token_val, code) for code in coupon_codes]
    coupon_results = await asyncio.gather(*tasks)
    update_sheet_range(f"O2:P{len(coupon_results)+1}", coupon_results)

    days_val = int(read_sheet_range("R5")[0][0])
    limit_val = int(read_sheet_range("R4")[0][0])
    endDate = datetime.now()
    startDate = endDate - timedelta(days=days_val - 1)
    startDate = startDate.replace(hour=0, minute=0, second=0, microsecond=0)
    startRow = find_row_with_yesterdays_date(startDate)

    clear_sheet_range(f"A{startRow}:I1000")
    clear_sheet_range("J2:K1000")

    couponIds = [row[0] for row in read_sheet_range("O2:O1000") if row]
    names = [row[0] for row in read_sheet_range("L2:L1000") if row]
    nameCodes = [row[0] for row in read_sheet_range("M2:M1000") if row]
    redeemCounts = []
    for row in read_sheet_range("P2:P1000"):
        try:
            redeemCounts.append(int(row[0]))
        except:
            redeemCounts.append(0)

    tasks_coupon = []
    for idx, couponId in enumerate(couponIds):
        if couponId:
            offset_val = redeemCounts[idx] - limit_val if redeemCounts[idx] > limit_val else 0
            tasks_coupon.append(fetch_coupon_data_async(token_val, couponId, limit_val, offset_val))
    responses = await asyncio.gather(*tasks_coupon, return_exceptions=True)

    couponDataByDate = {}
    for resp in responses:
        if isinstance(resp, Exception):
            continue
        coupon_data = resp.get("data", {}) \
                          .get("withAuth", {}) \
                          .get("user", {}) \
                          .get("coupon")
        if not coupon_data:
            continue
        redeems = coupon_data.get("redeems", [])
        couponCode = coupon_data.get("code", "")
        couponOwner = "Unknown"
        for i, nc in enumerate(nameCodes):
            if couponCode.endswith(nc):
                couponOwner = names[i]
                break
        for redeem in redeems:
            try:
                ts = int(redeem.get("settledAt"))
                redeemedAt = datetime.fromtimestamp(ts / 1000)
            except:
                continue
            if startDate <= redeemedAt <= endDate:
                dateKey = redeemedAt.strftime("%Y-%m-%d")
                if dateKey not in couponDataByDate:
                    couponDataByDate[dateKey] = {}
                if couponOwner not in couponDataByDate[dateKey]:
                    couponDataByDate[dateKey][couponOwner] = []
                couponDataByDate[dateKey][couponOwner].append({
                    "name": redeem.get("user", {}).get("name", ""),
                    "couponCode": couponCode,
                    "initialAmount": redeem.get("initialAmount", 0),
                    "discountAmount": redeem.get("discountAmount", 0),
                    "discountedAmount": redeem.get("discountedAmount", 0),
                    "coursename": (redeem.get("courses", [{}])[0]).get("name", "")
                })

    currentRow = startRow
    sortedDates = sorted(couponDataByDate.keys(), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))
    for dateKey in sortedDates:
        ownersData = couponDataByDate[dateKey]
        dateRowStart = currentRow
        update_sheet_range(f"A{currentRow}", [[format_date_to_ddmmyyyy(datetime.strptime(dateKey, '%Y-%m-%d'))]])
        for owner, coupons in ownersData.items():
            update_sheet_range(f"B{currentRow}", [[owner]])
            totalAmount = 0
            for i, coupon in enumerate(coupons):
                rowIndex = currentRow + i
                update_sheet_range(f"C{rowIndex}", [[coupon.get("name", "")]])
                update_sheet_range(f"D{rowIndex}", [[coupon.get("couponCode", "")]])
                update_sheet_range(f"E{rowIndex}", [[coupon.get("coursename", "")]])
                update_sheet_range(f"F{rowIndex}", [[coupon.get("initialAmount", 0)]])
                update_sheet_range(f"G{rowIndex}", [[coupon.get("discountAmount", 0)]])
                update_sheet_range(f"H{rowIndex}", [[coupon.get("discountedAmount", 0)]])
                totalAmount += coupon.get("discountedAmount", 0)
            update_sheet_range(f"I{currentRow}", [[totalAmount]])
            currentRow += len(coupons)
        currentRow += 1  
    memberNames = [row[0] for row in read_sheet_range("B2:B1000") if row]
    amounts = [row[0] for row in read_sheet_range("I2:I1000") if row]
    nameTotals = {}
    for i in range(len(memberNames)):
        name = memberNames[i]
        try:
            amount = float(amounts[i])
        except:
            amount = 0
        if name:
            nameTotals[name] = nameTotals.get(name, 0) + amount
    output = [[name, total] for name, total in nameTotals.items()]
    output.sort(key=lambda x: x[1], reverse=True)
    update_sheet_range(f"J2:K{len(output)+1}", output)


def run_process_coupon_updates():
    asyncio.run(process_coupon_updates())

@app.post("/update_coupon_data")
async def update_coupon_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_process_coupon_updates)
    return {"message": "Coupon update process started."}

@app.get("/")
def root():
    return {"message": "FastAPI Coupon Updater is running."}
