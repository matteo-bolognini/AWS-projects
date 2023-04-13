import json
import requests
import datetime
import boto3
import http.client

client = boto3.client('secretsmanager')

jamf_url = "MY_INSTANCE"

slack_url = "https://slack.com/api/chat.postMessage"
slack_channel = "#CHANNEL-NAME"
slack_headers = {
	"Authorization": f"Bearer {slack_api_token}",
	"Content-Type": "application/json; charset=utf-8"
}


def lambda_handler(event, context):
    response = client.get_secret_value(
        SecretId='prod/MY_SECRET_MANAGER_VAULT')
        
    secretDict = json.loads(response['SecretString'])
    
    api_user = secretDict['MY-USER']
    api_password = secretDict['MY-PASSWORD']
    slack_token = secretDict['MY_SLACK_TOKEN']
    
    output = json.loads(event["body"])
    
    serial_number = output['event']['serialNumber']
    jss_id = output['event']['jssID']
    device_udid = output['event']['udid']
    
    print(f"Serial Number: {serial_number}")
    print(f"JSS ID: {jss_id}")
    print(f"UDID: {device_udid}")
    
    token_url = f"https://{jamf_url}.pub.jamf.build/api/v1/auth/token"
    headers = {"Accept": "application/json"}

    resp = requests.post(token_url, auth=(api_user, api_password), headers=headers)
    resp.raise_for_status()

    resp_data = resp.json()
    print(f"Access token granted, valid until {resp_data['expires']}.")

    data = resp.json()
    token = data["token"]
    resp = requests.get(
        f"https://{jamf_url}.jamfcloud.com/JSSResource/computers/serialnumber/{serial_number}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )

    if resp.status_code != 401:
        resp_json = resp.json()
        device_id = resp_json["computer"]["general"].get("id")
    else:
        print("Check your credentials")
    
    print(f"Device ID: {device_id}")
    
    url = f"https://{jamf_url}.jamfcloud.com/api/v1/computers-inventory?section=HARDWARE&page=0&page-size=100&filter=hardware.serialNumber%3D%3D%22{serial_number}%22"
    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    resp = requests.get(url, headers=headers)
    resp_json = resp.json()
    print(f"API GET response: {resp_json}")
    
    resp_json = resp.text
    
    output = json.loads(resp_json)
    
    total_count = output["totalCount"]
    print(f"Total Count : {total_count}")
    
    id_multiple = []
    for result in output["results"]:
        id = result["id"]
        id_multiple.append(id)
    print(f"JSS device IDs : {id_multiple}")
    
    id_multiple = list(map(int, id_multiple))
    id_multiple.sort()
    
    id1 = id_multiple[0]
    id2 = id_multiple[1]
    
    udid_multiple = []
    for result in output["results"]:
        udid = result["udid"]
        udid_multiple.append(udid)
    print(f"UDIDs : {udid_multiple}")
    
    udid_multiple.sort()
    
    udid1 = udid_multiple[0]
    udid2 = udid_multiple[1]

    
    payload = {
        "channel": slack_channel,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*A duplicated Computer record has been detected:*",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*SerialNumber:*\n{serial_number}",
                    },
                    {"type": "mrkdwn", "text": f"*Device Record Count:*\n{total_count}"},
                    ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*UDID First Record:*\n{udid1}"},
                    {"type": "mrkdwn", "text": f"*UDID Second Record:*\n{udid2}"},
                    ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*<https://{jamf_url}.jamfcloud.com/computers.html?id={id1}&o=r|Old Computer Record>*",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*<https://{jamf_url}.jamfcloud.com/computers.html?id={id2}&o=r|New Computer Record - DeviceEnrolled>*",
                    },
                    ],
            },
            ],
            "attachments": [
                {
                    "text": "WARNING: The below action cannot be undone, choose wisely!",
                    "fallback": "Click the below button if you want to delete the old record in Jamf Pro",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "callback_id": f"{udid1}",
                    "actions": [
                        {
                            "name": f"{serial_number}",
                            "text": f"Delete Old Record: ID {id1}",
                            "type": "button",
                            "value": f"{id1}"
                        },
                        ]
                }
                ]
    }
    response = requests.post(slack_url, headers=slack_headers, json=payload)
    
    if response.status_code == 200 and response.json().get("ok"):
        print(f"Message successfully posted to {slack_channel}")
        print(f"Slack Webhook Post HTTP response: {slack_resp.status_code}")
    else:
        print("Error posting message to Slack:", response.json())


    return {
        'statusCode': 200,
        'body': json.dumps('Success')
    }
