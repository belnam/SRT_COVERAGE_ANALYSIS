from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect,Query,APIRouter, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import StreamingResponse
import httpx
from io import BytesIO
import pandas as pd
import requests
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from multiprocessing.pool import ThreadPool
from fastapi.middleware.cors import CORSMiddleware
import os
from routers import srt_summary_stats_route
from dotenv import load_dotenv
import io
from datetime import datetime,timedelta
from tenacity import retry, stop_after_attempt, wait_fixed
import glob
import asyncio
import traceback
from datetime import datetime
from helpers.api_url import get_url
from crud import srtcrud
from middleware.dependencies import get_db
from schemas import srt_summary_stats_schema
from sqlmodel import Session
from sqlmodel import select
from model import srt_summary_stats_model
import json

load_dotenv()
app = FastAPI()

os.makedirs("processed_files", exist_ok=True)
os.makedirs("graphs", exist_ok=True)

"""" Initialize an empty list to store WebSocket clients"""
websocket_clients = []
token = None

origins = [
    "*"  
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],

)

app.include_router(srt_summary_stats_route.router)

@app.websocket("/ws/weekly-stats/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websocket_clients.append(websocket)
    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)

"""Delete files older than 7 days from processed_files/."""
async def cleanup_old_files():
    folder_path = "processed_files"
    now = datetime.now()
    cutoff = now - timedelta(days=7)  
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mtime < cutoff:
                os.remove(file_path)
                print(f"🗑️ Deleted old file: {file_path}")

"""Fetches and returns the latest weekly statistics."""
async def get_weekly_stats(db: Session):

    return srt_summary_stats_route.get_srt_summary_stats(db)
 

"""Send real-time updates to all connected WebSocket clients."""
async def broadcast_update():
    db = next(get_db())
    try:
        data = await get_weekly_stats(db)
        for client in websocket_clients:
            try:
                await client.send_json(data)
            except Exception:
                websocket_clients.remove(client)
    finally:
        db.close()



"""connecting to LP graphqgl api"""
@retry(stop=stop_after_attempt(3), wait= wait_fixed(2))

async def generate_api_token():
    service_url = get_url()
    transport = AIOHTTPTransport(url=service_url)
    client = Client(transport=transport, fetch_schema_from_transport=True)

    username = os.getenv("INNOVATIVE_USERNAME")
    password = os.getenv("INNOVATIVE_PASSWORD")

    if not username or not password:
        raise ValueError("Username or password environment variables not set.")

    query = gql('''
        mutation LoginEmployee($username: String!, $password: String!) {
            loginEmployee(username: $username, password: $password) {
                authData {
                    token
                }
            }
        }
    ''')
    variables = {"username": username, "password": password}
    
    result = await client.execute_async(query, variable_values=variables)
    return result['loginEmployee']['authData']['token']

@app.on_event("startup")
async def startup_tasks():
    global token
    try:
        token = await generate_api_token()
        print("✅ API Token generated successfully!")
    except Exception as e:
        print(f"❌ Failed to generate API token: {e}")
    asyncio.create_task(cleanup_old_files())

"""Check if assets exsts for a given lp from the AAP API."""
def check_asset_exists(args):
    license_plate, state = args
    url = "https://amazon.backend.innovativetoll.com/check-asset-exists"
    try:
        response = requests.post(url, json={"license_plate": license_plate, "license_plate_state": state})
        response.raise_for_status()
        data = response.json().get('data', {})
        exists = data.get('exists') is True 
        purchase_type = data.get('data', {}).get('purchase_type', None) if isinstance(data.get('data'), dict) else None
        print(f"✅ Checked {license_plate}-{state}: exists={exists}, purchase_type={purchase_type}")
        return license_plate, state, exists, purchase_type
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed for {license_plate}-{state}: {e}")
        return license_plate, state, False, None
    
""" query to fetch toll agency account for a given LP from the GraphQL API."""   
def get_accounts_from_license_plate(args):
    license_plate, state = args
    try:
        service_url = get_url()
        # transport = AIOHTTPTransport(url=service_url, headers={"Authorization": token}, ssl=False)
        transport = AIOHTTPTransport(url=service_url, headers={"Authorization": token})
        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql('''
            mutation Mutation($licensePlate: String!, $state: String!) {
                accountsBasedOnLicensePlate(license_plate: $licensePlate, state: $state) {
                    data {
                        agency { agency_name }
                        account { account_name }
                    }
                }
            }
        ''')
        variables = {"licensePlate": license_plate, "state": state}
        result = client.execute(query, variable_values=variables)
        accounts_data = result.get('accountsBasedOnLicensePlate', {}).get('data', [])
        return ", ".join(f"{entry['agency']['agency_name']}_{entry['account']['account_name']}" for entry in accounts_data) if accounts_data else ""
    except:
        return ""
    
"""query to fetch account_agency_name for a given agency from the GraphQL API."""
def fetch_account_agency_coverages(agency_name):
    global token
    try:
        service_url = get_url()
        transport = AIOHTTPTransport(url=service_url, headers={"Authorization": token})
        # transport = AIOHTTPTransport(url=service_url, headers={"Authorization": token}, ssl=False)

        client = Client(transport=transport, fetch_schema_from_transport=True)
        query = gql('''
            query AccountAgencyCoverages($filter: AccountAgencyCoverageFilter) {
                accountAgencyCoverages(filter: $filter) {
                    account_agency_coverage_id
                    account_agency_id {
                        agency_name   # ✅ Correct field
                        account_agency_id
                    }
                    agency_id {
                        agency_id
                        agency_name
                        state_id {
                            state_id
                            state_name
                            abbreviation
                        }
                    }
                }
            }
        ''')
        variables = {
            "filter": {
                "agency_name": agency_name,
                "account_agency_name": None,
                "state_abbreviation": None
            }
        }
        result = client.execute(query, variable_values=variables)
    
        accounts = [
            account["account_agency_id"]["agency_name"]
            for account in result.get("accountAgencyCoverages", [])
            if account.get("account_agency_id") and account["account_agency_id"].get("agency_name")
        ]

        return ", ".join(accounts) if accounts else ""
    except Exception as e:
        print(f"❌ Error fetching account agency coverages for {agency_name}: {e}")
        return ""
    
"""Processes uploaded SRT and Subagency files, stores reports, and notifies clients in real-time."""
@app.post("/upload/")
async def process_files(srt_file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        srt_content = await srt_file.read()
        srt_df = pd.read_excel(io.BytesIO(srt_content), engine="openpyxl", dtype=str)
        srt_df.columns = [col.strip().upper().replace("\xa0", " ").replace("\n", " ").replace("\t", " ") for col in srt_df.columns]
        srt_df['LICENSE PLATE'] = srt_df['LICENSE PLATE'].astype(str)

        """Checking if assets exists in AAP API, categorize into two categories  InAAP ,NotInAAP those in  InAAP  are further categorized as InAAP_Bought & nAAP_Leased and find their count using multiprocessing """
        with ThreadPool(50) as pool:
            results = pool.map(check_asset_exists, zip(srt_df['LICENSE PLATE'], srt_df['STATE']))
        srt_df['In AAP'], srt_df['Purchase Type'] = zip(*[(exists, purchase_type) for _, _, exists, purchase_type in results])
        srt_df['In AAP'] = srt_df['In AAP'].astype(bool)  
        InAAP = srt_df[srt_df["In AAP"]==True]
        NotInAAP = srt_df[srt_df['In AAP'] == False]
        InAAP_Bought = InAAP[InAAP['Purchase Type'] == 'Bought']
        InAAP_Leased = InAAP[InAAP['Purchase Type'] == 'Leased']
        total_plates = len(NotInAAP)+ len(InAAP_Bought) + len(InAAP_Leased)
        total_not_in_aap = len(NotInAAP)
        total_in_aap_bought = len(InAAP_Bought)
        total_in_aap_leased = len(InAAP_Leased)

        """Fetching accounts for InAAP_Bought and adding a new column called All accounts to the dataframe from the graphql api"""
        with ThreadPool(50) as pool:
            accounts_results = pool.map(get_accounts_from_license_plate, zip(InAAP_Bought['LICENSE PLATE'], InAAP_Bought['STATE']))
        srt_df.loc[InAAP_Bought.index, 'All Accounts'] = accounts_results
        srt_df["All Accounts"].fillna("No Account Found", inplace=True) 
        InAAP_Bought_with_accounts = srt_df.loc[InAAP_Bought.index].copy()
        global token
        if not token:
            raise HTTPException(status_code=500, detail="🚨 API token not available!")

        """Fetching  RECOMMENDED account for each agency and appending a column called RECOMMENDED_ACCOUNTS to InAAP_Bought_with_accounts dataframe from AccountAgencyCoverages graphql api """
        if "AGENCY" in InAAP_Bought_with_accounts.columns:
            with ThreadPool(50) as pool:
                recommended_accounts_results = pool.map(fetch_account_agency_coverages,InAAP_Bought_with_accounts["AGENCY"].unique())
            agency_accounts_map = dict(zip(InAAP_Bought_with_accounts["AGENCY"].unique(),recommended_accounts_results ))
            InAAP_Bought_with_accounts["RECOMMENDED_ACCOUNTS"] = InAAP_Bought_with_accounts["AGENCY"].map(agency_accounts_map)
        else:
            print("⚠️ 'AGENCY' column missing. Cannot assign recommended accounts.")

        """
        Processes vehicle and account data by selecting relevant columns, formating column names to lp template,. Includes a helper function
        `has_partial_match` that checks if any recommended account partially matches or is partially 
        matched by any of the existing accounts in the 'All Accounts' field,and dropping match columns and retaining the unmatched columns dtaframe.
        """

        def has_partial_match(row):
            all_accounts = [acc.strip().lower() for acc in str(row['All Accounts']).split(',') if acc.strip()]
            recommended_accounts = [rec.strip().lower() for rec in str(row['RECOMMENDED_ACCOUNTS']).split(',') if rec.strip()]
            return any(
                rec in acc or acc in rec
                for rec in recommended_accounts
                for acc in all_accounts
            )
        columns_to_keep = [
            "LICENSE PLATE", "STATE", "AGENCY", "TRANSPONDER", "All Accounts", "RECOMMENDED_ACCOUNTS"
        ]
        if 'All Accounts' in InAAP_Bought_with_accounts.columns:
            final_df = InAAP_Bought_with_accounts[columns_to_keep].copy()
        else:
            raise KeyError("'All Accounts' column is missing in DataFrame")
        
        final_df.rename(columns={
            'LICENSE PLATE': 'License Plate',
            'STATE': 'LP State',
            'AGENCY': 'Agency',
            'TRANSPONDER':'Transponder',
            'All Accounts':'All Accounts',
            'RECOMMENDED_ACCOUNTS': 'RECOMMENDED_ACCOUNTS'
        }, inplace=True)
        additional_columns = ['Year', 'Make', 'Model', 'Color', 'Start Date/Time', 'End Date/Time', 'Status','Account','Client', 'Country']
        for col in additional_columns:                                    
            final_df[col] = ''  
        final_columns = [
            'License Plate', 'LP State', 'Year', 'Make', 'Model', 'Color',
            'Transponder', 'Start Date/Time', 'End Date/Time', 'Status', 'Agency',
            'Account', 'Client', 'Country', 'All Accounts','RECOMMENDED_ACCOUNTS'
        ]

        current_week = srt_df["WEEK"].iloc[0]  
        current_year = srt_df["YEAR"].iloc[0] 

        final_df = final_df[final_columns].drop_duplicates(subset=['License Plate'])
        filtered_df = final_df[~final_df.apply( has_partial_match, axis=1)].copy()
        timestamp = int(datetime.now().timestamp())
        year_week = f"{current_year}_Week{current_week}"
        InAAP_Bought.to_excel(f"processed_files/InAAP_Bought_{year_week}_{timestamp}.xlsx", index=False)
        NotInAAP.to_excel(f"processed_files/NotInAAP_{year_week}_{timestamp}.xlsx", index=False)
        InAAP_Leased.to_excel(f"processed_files/InAAP_Leased_{year_week}_{timestamp}.xlsx", index=False)
        filtered_df.to_excel(f"processed_files/LPs_to_be_added_to_account_{year_week}_{timestamp}.xlsx", index=False)
 
        headers= {'Authorization': '45921csdvsVadfadsf07nLG4kdSTXHj2314oYpDqL29ENHSML'}
        requests.post("https://s3.innovativetoll.com/fs/srt_analysis", files={'file': open(f"processed_files/InAAP_Bought_{year_week}_{timestamp}.xlsx", "rb")}, headers=headers)
        requests.post("https://s3.innovativetoll.com/fs/srt_analysis", files={'file': open(f"processed_files/NotInAAP_{year_week}_{timestamp}.xlsx", "rb")}, headers=headers)
        requests.post("https://s3.innovativetoll.com/fs/srt_analysis", files={'file': open(f"processed_files/InAAP_Leased_{year_week}_{timestamp}.xlsx", "rb")}, headers=headers)
        requests.post("https://s3.innovativetoll.com/fs/srt_analysis", files={'file': open(f"processed_files/LPs_to_be_added_to_account_{year_week}_{timestamp}.xlsx", "rb")}, headers=headers)

        """Saving the SRT Summary Statistics to the database"""
        db_payload = srt_summary_stats_schema.SRTStatSchema({
            "lp_counts": total_plates,
            "not_in_aap": total_not_in_aap,
            "aap_bought": total_in_aap_bought,
            "aap_leased": total_in_aap_leased,
            "week": current_week,
            "year": current_year
        })
        print(db_payload)
        summary_obj = srtcrud.add_summary_stats(db, summary=db_payload)
        if not summary_obj:
            return JSONResponse(status_code=404, content={"message": "Failed to add summary statistics."})
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"processed_files/AAP_Report_{timestamp}.xlsx"
        srt_df.to_excel(file_path, index=False)
        await broadcast_update()
        return {"message": "File processed successfully", "report_path": file_path}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"❌ Error: {str(e)}")

"""FastAPI API for listing all processed report"""
@app.get("/list-reports/")
async def list_reports():
    """Lists all stored reports."""
    files = glob.glob("processed_files/*.xlsx")
    return {"reports": [os.path.basename(file) for file in files]}

"""FastAPI API for downloading processed report"""
@app.get("/download/{report_type}")
async def download_report(report_type: str):
    """Allows downloading reports from S3 without specifying full filenames."""
    valid_reports = ["InAAP_Bought", "NotInAAP", "InAAP_Leased", "LPs_to_be_added_to_account"]
    if report_type not in valid_reports:
        raise HTTPException(status_code=400, detail="Invalid report type")
    s3_url = f"https://s3.innovativetoll.com/fs/srt_analysis?filename={report_type}.xlsx"
    headers = {
        "Authorization": "45921csdvsVadfadsf07nLG4kdSTXHj2314oYpDqL29ENHSML"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(s3_url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="File not found on S3")
    return StreamingResponse(
        BytesIO(response.content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{report_type}.xlsx"'}
    )


"""FastAPI API for fetching the weekly summary statistics  line graph data by year and week filter"""
@app.get("/weekly-stats-graph/")
async def weekly_stats_graph(
    year: int = Query(..., description="Filter by year"),
    start_week: int = Query(..., description="Start week filter"),
    end_week: int = Query(..., description="End week filter"),
    db: Session = Depends(get_db)
):
    stmt = (
        select(srt_summary_stats_model.SRTSummaryStats)
        .where(srt_summary_stats_model.SRTSummaryStats.year == year)
        .where(srt_summary_stats_model.SRTSummaryStats.week >= start_week)
        .where(srt_summary_stats_model.SRTSummaryStats.week <= end_week)
        .order_by(srt_summary_stats_model.SRTSummaryStats.year, srt_summary_stats_model.SRTSummaryStats.week)
    )

    records = db.execute(stmt).scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail="No data available for the selected filters")

    seen = set()
    unique_records = []
    for r in records:
        key = (r.year, r.week)
        if key not in seen:
            seen.add(key)
            unique_records.append(r)

    response = []
    for row in unique_records:
        try:
            response.append({
                "value": [
                    {"report_type": "In AAP Bought", "count": int(row.aap_bought)},
                    {"report_type": "In AAP Leased", "count": int(row.aap_leased)},
                    {"report_type": "Not in AAP", "count": int(row.not_in_aap)},
                ]
            })
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Data format error: {e}")

    return {"weeklyTollSpendChart": response}


"""FastAPI API for fetching the current week summary statistics  piechart data by year filter"""
@app.get("/weekly-pie-chart/")
async def weekly_pie_chart(
    year: int = Query(None, description="Filter by year"),
    week: int = Query(None, description="Filter by specific week"),
    db: Session = Depends(get_db)
):
    stmt = select(srt_summary_stats_model.SRTSummaryStats)

    if year is not None:
        stmt = stmt.where(srt_summary_stats_model.SRTSummaryStats.year == year)
    if week is not None:
        stmt = stmt.where(srt_summary_stats_model.SRTSummaryStats.week == week)

    results = db.execute(stmt).scalars().all()

    if not results:
        raise HTTPException(status_code=404, detail="No data available for the selected filters")

    latest_record = results[-1]
    try:
        result = {
            "value": [
                {"report_type": "In AAP Bought", "count": int(latest_record.aap_bought)},
                {"report_type": "In AAP Leased", "count": int(latest_record.aap_leased)},
                {"report_type": "Not in AAP", "count": int(latest_record.not_in_aap)},
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data parsing error: {e}")

    return {"weeklyPieChart": result}


#uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug, http://10.2.250.88:8000/docs
# uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug