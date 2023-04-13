import requests
import json
import boto3
import http.client
import urllib.parse

client = boto3.client('MY_SECRET_MANAGER')

jamf_url = "MY_INSTANCE"
control_group = "MY_LDAP_GROUP"
cloud_idp_id = "MY-CLOUD_IDP_ID"

def lambda_handler(event, context):
    
    response = client.get_secret_value(
        SecretId='prod/MY_SECRET_MANAGER_VAULT')
        
    secretDict = json.loads(response['SecretString'])
    
    api_user = secretDict['MY_USER']
    api_password = secretDict['MY_PASSWORD']

    request_body = event["body"]
    request_body_parsed = request_body.replace('payload=','', 1)
    request_body_parsed = urllib.parse.unquote(request_body_parsed)
    request_body_parsed = json.loads(request_body_parsed)
    
    print(f"request_body_parsed: {request_body_parsed}")
    
    device_id = request_body_parsed["actions"][0]["value"]
    serial_number = request_body_parsed["actions"][0]["name"]
    udid = request_body_parsed["callback_id"]
    username = request_body_parsed["user"]["name"]
    
    print(f"UDID:{udid}")
    print(f"Serial Number: {serial_number}")
    print(f"Device ID: {device_id}")
    print(f"Username: {username}")
    
    token_url = f"https://{jamf_url}.jamfcloud.com/api/v1/auth/token"
    headers = {"Accept": "application/json"}
    
    resp = requests.post(token_url, auth=(api_user, api_password), headers=headers)
    resp.raise_for_status()
    resp_data = resp.json()
    print(f"Access token granted, valid until {resp_data['expires']}.")
    
    data = resp.json()
    token = data["token"]
    
    url = f"https://{jamf_url}.jamfcloud.com/api/v1/cloud-idp/{cloud_idp_id}/test-user-membership"
    payload = {
        "username": f"{username}",
        "groupname": f"{control_group}"
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
        "content-type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    resp_data = response.json()
    is_member = resp_data.get("isMember")
    
    if is_member:
        print("isMember is True")
        
        return {
            'statusCode': 200,
            'body': (f"A device record has been deleted via Slack integration, details as following:\n\nDevice Record ID {device_id}\n\nDuplicate Serial Number: {serial_number}\nUDID:{udid}\n\nDeleted from Jamf Pro by user: {username}")
        }
    
    else:
        print("isMember is not True")
        print(f"{username} attempted to delete device record:{device_id} with Serial Number:{serial_number} but is not authorized as is not member of the {control_group} LDAP Group.")
        
        return {
        'statusCode': 200,
        'body': (f"Account:{username} attempted to delete the device record:{device_id} but is not authorized due to lack of permissions, contact your Jamf Pro administrator.")
    }
