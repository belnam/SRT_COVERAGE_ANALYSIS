import pandas as pd
import requests
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
from multiprocessing.pool import ThreadPool
from dotenv import load_dotenv  
import os


load_dotenv()

def get_url():
    return "https://violations.innovativetoll.com/api"
            

def generate_token():
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
    result = client.execute(query, variable_values=variables)
    return result['loginEmployee']['authData']['token']

token = generate_token()

def check_asset_exists(args):
    license_plate, state = args
    url = "https://amazon.backend.innovativetoll.com/check-asset-exists"
    try:
        response = requests.post(url, json={"license_plate": license_plate, "license_plate_state": state})
        response.raise_for_status()
        data = response.json().get('data', {})
        exists = data.get('exists', False)
        purchase_type = data.get('data', {}).get('purchase_type', None) if isinstance(data.get('data'), dict) else None
        return license_plate, state, exists, purchase_type
    except requests.exceptions.RequestException:
        return license_plate, state, False, None

def get_accounts_from_license_plate(args):
    license_plate, state = args
    try:
        service_url = get_url()
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

SRT = pd.read_excel("Processed SRTs WK6 1.xlsx")
SRT['LICENSE PLATE'] = SRT['LICENSE PLATE'].astype(str)

print("Checking license plates against the endpoint...")
with ThreadPool(30) as pool:
    results = pool.map(check_asset_exists, zip(SRT['LICENSE PLATE'], SRT['STATE']))

SRT['In AAP'], SRT['Purchase Type'] = zip(*[(exists, purchase_type) for _, _, exists, purchase_type in results])
SRT['In AAP'] = SRT['In AAP'].astype(bool)  

InAAP = SRT[SRT['In AAP'] == True]
NotInAAP = SRT[SRT['In AAP'] == False]

InAAP_Bought = InAAP[InAAP['Purchase Type'] == 'Bought']
InAAP_Leased = InAAP[InAAP['Purchase Type'] == 'Leased']

print("Fetching accounts for InAAP_Bought")
with ThreadPool(50) as pool:
    accounts_results = pool.map(get_accounts_from_license_plate, zip(InAAP_Bought['LICENSE PLATE'], InAAP_Bought['STATE']))

InAAP_Bought['All Accounts'] = accounts_results

sub_agencies_df = pd.read_excel("SubAgencies_to_Agencies.xlsx")
sub_agencies_df.columns = ["SUB_AGENCY", "AGENCY_STATE", "AGENCY", "RECOMMENDED_ACCOUNTS"]

merged_df = InAAP_Bought.merge(
    sub_agencies_df,
    left_on=['AGENCY', 'AGENCY STATE'],
    right_on=['SUB_AGENCY', 'AGENCY_STATE'],
    how='left'

)
merged_df['RECOMMENDED_ACCOUNTS'] = merged_df['RECOMMENDED_ACCOUNTS'].combine_first(
    InAAP_Bought.merge(
        sub_agencies_df,
        left_on=['AGENCY', 'AGENCY STATE'],
        right_on=['AGENCY', 'AGENCY_STATE'],
        how='left'
    )['RECOMMENDED_ACCOUNTS']
)

print("adding recommended accounts")
def has_partial_match(row):
    all_accounts = [acc.strip().lower() for acc in str(row['All Accounts']).split(',') if acc.strip()]
    recommended_accounts = [rec.strip().lower() for rec in str(row['RECOMMENDED_ACCOUNTS']).split(',') if rec.strip()]
    return any(
        rec in acc or acc in rec
        for rec in recommended_accounts
        for acc in all_accounts
    )

columns_to_keep = [
    'LICENSE PLATE', 'STATE', 'AGENCY_x', 'AGENCY STATE', 'All Accounts', 'RECOMMENDED_ACCOUNTS'
]
merged_df = merged_df[columns_to_keep]
merged_df.rename(columns={
    'LICENSE PLATE': 'License Plate',
    'STATE': 'LP State',
    'AGENCY_x': 'Agency',
    'All Accounts':'All Accounts', 
    'RECOMMENDED_ACCOUNTS': 'RECOMMENDED_ACCOUNTS'
}, inplace=True)

additional_columns = ['Year', 'Make', 'Model', 'Color', 'Transponder', 'Start Date/Time', 'End Date/Time', 'Status','Account','Client', 'Country']
for col in additional_columns:                                     
    merged_df[col] = ''  

final_columns = [
    'License Plate', 'LP State', 'Year', 'Make', 'Model', 'Color',
    'Transponder', 'Start Date/Time', 'End Date/Time', 'Status', 'Agency',
    'Account', 'Client', 'Country', 'All Accounts','RECOMMENDED_ACCOUNTS'
]

final_df = merged_df[final_columns].drop_duplicates(subset=['License Plate'])
filtered_df = final_df[~final_df.apply( has_partial_match, axis=1)].copy()

InAAP_Bought.to_excel("InAAP_Bought_with_Accounts6.xlsx", index=False)
InAAP_Leased.to_excel("InAAP_Leased6.xlsx", index=False)
NotInAAP.to_excel("NotInAAP6.xlsx", index=False)
filtered_df.to_excel("unique_LP_recommendations_filtered6.xlsx", index=False)




