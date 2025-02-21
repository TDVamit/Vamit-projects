import asyncio
import base64
import httpx
import logging
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

app = FastAPI()

# WooCommerce API URLs & credentials
BASE_URL = "https://your-domain.com/wp-json/wc/v3/products"
CATEGORY_URL = "https://your-domain.com/wp-json/wc/v3/products/categories"
CONSUMER_KEY = "YOUR_CONSUMER_KEY"
CONSUMER_SECRET = "YOUR_CONSUMER_SECRET"
AUTH = base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()

# Course API base URL (includes any token information if needed)
COURSE_API_BASE = "https://api.example.com/v2/course/preview/similar/BASE64_ENCODED_TOKEN"

# Google Sheets configuration
SERVICE_ACCOUNT_FILE = "path/to/your/service_account.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"
SHEET_NAME = "Sheet1"

def get_sheet_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

sheet_service = get_sheet_service()
sheet = sheet_service.spreadsheets()

def read_sheet_range(range_name: str):
    result = sheet.values().get(
        spreadsheetId=SPREADSHEET_ID, 
        range=f"{SHEET_NAME}!{range_name}"
    ).execute()
    return result.get("values", [])

def update_sheet_range(range_name: str, values):
    body = {"values": values}
    sheet.values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{range_name}",
        valueInputOption="RAW",
        body=body
    ).execute()

def append_sheet_row(row_values):
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:Z",
        valueInputOption="RAW",
        body={"values": [row_values]}
    ).execute()

def clear_sheet_range(range_name: str):
    sheet.values().clear(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!{range_name}"
    ).execute()

def get_sheet_data():
    data = sheet.getDataRange().execute()
    values = data.get("values", [])
    if not values:
        return []
    headers = values[0]
    data_rows = []
    for row in values[1:]:
        data_rows.append({
            "id": row[0] if len(row) > 0 else "",
            "name": row[1] if len(row) > 1 else "",
            "description": row[2] if len(row) > 2 else "",
            "imageUrl": row[3] if len(row) > 3 else "",
            "price": row[4] if len(row) > 4 else "",
            "discount": row[5] if len(row) > 5 else "",
            "finalPrice": row[6] if len(row) > 6 else "",
            "categories": row[7] if len(row) > 7 else "",
            "singlePaymentLink": row[8] if len(row) > 8 else "",
            "lastSeen": row[9] if len(row) > 9 else "",
            "productid": row[10] if len(row) > 10 else ""
        })
    return data_rows

def update_productid_in_sheet(row_index: int, product_id):
    update_sheet_range(f"K{row_index+2}", [[product_id]])

async def fetch_with_retries(url: str, max_retries=5, sleep_seconds=2):
    attempts = 0
    async with httpx.AsyncClient() as client:
        while attempts < max_retries:
            try:
                response = await client.get(url, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                attempts += 1
                logging.error(f"Attempt {attempts} failed for URL {url}: {e}")
                if attempts < max_retries:
                    await asyncio.sleep(sleep_seconds)
        raise HTTPException(status_code=500, detail="Max retries reached for URL: " + url)

async def process_course_updates():
    total_count_url = f"{COURSE_API_BASE}?filterId=[1]&sortId=[7]&subCatList[]=&mainCategory=0&limit=1&offset=0"
    data = await fetch_with_retries(total_count_url)
    if data.get("status") != "success":
        raise HTTPException(status_code=500, detail="Failed to fetch total count")
    total_count = data.get("data", {}).get("totalCount")
    if not total_count:
        raise HTTPException(status_code=500, detail="No totalCount in response")
    
    all_courses_url = f"{COURSE_API_BASE}?filterId=[1]&sortId=[7]&subCatList[]=&mainCategory=0&limit={total_count}&offset=0"
    data_all = await fetch_with_retries(all_courses_url)
    if data_all.get("status") != "success":
        raise HTTPException(status_code=500, detail="Failed to fetch all courses data")
    courses = data_all.get("data", {}).get("coursesData", [])
    
    existing_data = get_sheet_data()
    fetched_courses_map = {course["id"]: course for course in courses}
    today = datetime.now().isoformat()[:10]
    
    for index, row in enumerate(existing_data):
        course = fetched_courses_map.get(row["id"])
        if course:
            updated = False
            if row["name"] != course["name"]:
                row["name"] = course["name"]
                updated = True
            if row["description"] != course["description"]:
                row["description"] = course["description"]
                updated = True
            if row["imageUrl"] != course["imageUrl"]:
                row["imageUrl"] = course["imageUrl"]
                updated = True
            if row["price"] != course["price"]:
                row["price"] = course["price"]
                updated = True
            if row["discount"] != course["discount"]:
                row["discount"] = course["discount"]
                updated = True
            if row["finalPrice"] != course["finalPrice"]:
                row["finalPrice"] = course["finalPrice"]
                updated = True
            if row["categories"] != course["categories"]:
                row["categories"] = course["categories"]
                updated = True
            if row["singlePaymentLink"] != course["singlePaymentLink"]:
                row["singlePaymentLink"] = course["singlePaymentLink"]
                updated = True
            row["lastSeen"] = today
            if not row["productid"]:
                await create_product(row, index)
            else:
                if updated:
                    await update_product(row)
            fetched_courses_map.pop(row["id"], None)
    
    for course in fetched_courses_map.values():
        new_row = [
            course["id"],
            course["name"],
            course["description"],
            course["imageUrl"],
            course["price"],
            course["discount"],
            course["finalPrice"],
            course["categories"],
            course["singlePaymentLink"],
            today,
            ""  
        ]
        append_sheet_row(new_row)
    
    await handle_missing_data(existing_data)
    logging.info("Course data updated successfully.")

async def create_product(row, index):
    category_ids = await create_ids(row)
    product_data = {
        "name": row["name"],
        "type": "external",
        "external_url": row["singlePaymentLink"],
        "button_text": "Buy Now",
        "regular_price": str(row["price"]),
        "sale_price": str(row["finalPrice"]),
        "categories": category_ids,
        "description": row["description"],
        "short_description": row["description"],
        "images": [{"src": row["imageUrl"]}]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BASE_URL,
            json=product_data,
            headers={
                "Authorization": f"Basic {AUTH}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()
        product_response = response.json()
        product_id = product_response.get("id")
        update_productid_in_sheet(index, product_id)

async def update_product(row):
    product_update_data = {
        "name": row["name"],
        "type": "external",
        "external_url": row["singlePaymentLink"],
        "button_text": "Buy Now",
        "regular_price": str(row["price"]),
        "sale_price": str(row["finalPrice"]),
        "categories": await create_ids(row),
        "description": row["description"],
        "short_description": row["description"],
        "images": [{"src": row["imageUrl"]}]
    }
    update_url = f"{BASE_URL}/{row['productid']}"
    async with httpx.AsyncClient() as client:
        response = await client.put(
            update_url,
            json=product_update_data,
            headers={
                "Authorization": f"Basic {AUTH}",
                "Content-Type": "application/json"
            }
        )
        response.raise_for_status()

async def create_ids(row):
    category_names = [name.strip() for name in row["categories"].split(',')] if row["categories"] else []
    category_ids = []
    category_map = get_category_map()
    for cat_name in category_names:
        if cat_name in category_map:
            category_ids.append({"id": category_map[cat_name]})
        else:
            category_data = {"name": cat_name}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    CATEGORY_URL,
                    json=category_data,
                    headers={
                        "Authorization": f"Basic {AUTH}",
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                cat_response = response.json()
                cat_id = cat_response.get("id")
                category_ids.append({"id": cat_id})
                update_category_map(cat_name, cat_id)
    return category_ids

async def handle_missing_data(existing_data):
    threshold_days = 15
    current_date = datetime.now()
    for row in existing_data:
        if row["lastSeen"]:
            try:
                last_seen_date = datetime.fromisoformat(row["lastSeen"])
            except Exception:
                continue
            if (current_date - last_seen_date).days > threshold_days:
                await delete_product(row)

async def delete_product(row):
    product_id = row.get("productid")
    if product_id:
        delete_url = f"{BASE_URL}/{product_id}?force=true"
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                delete_url,
                headers={
                    "Authorization": f"Basic {AUTH}",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()

def get_category_map():
    data = read_sheet_range("L2:M")
    category_map = {}
    for row in data:
        if len(row) >= 2:
            try:
                category_map[row[1]] = int(row[0])
            except:
                continue
    return category_map

def update_category_map(category_name, cat_id):
    append_sheet_row([cat_id, category_name])


### FASTAPI ENDPOINT
@app.post("/update_course_data")
async def update_course_data_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(process_course_updates)
    return {"message": "Course update process started."}

@app.get("/")
def read_root():
    return {"message": "FastAPI Course Updater is running."}
