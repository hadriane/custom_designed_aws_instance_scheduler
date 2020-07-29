from botocore.exceptions import ClientError
from datetime import date
import datetime
import boto3
import pyjq
import pytz
import json
import requests



# ####----VARIABLES----#### #

# User defined variables
shutdown_days = ["Saturday", "Sunday"]  # Enter the days for full day shutdown
day_to_get_holidays = 'Saturday'  # Enter the day you want to GET holidays from Google Calendar API
shutdown_window = ["22:30", "06:35"]  # Enter the time interval for weekdays shutdown in 24hr time format
time_zone = 'Asia/Kuala_Lumpur'  # Enter timezone here
ec2_dryrun = True  # Set to True to dryrun start/stop EC2 instances
ec2_tag_value = 'qwerty_auto_schedule'  # Enter tag value to search EC2 instances against

# Enter Google Calender API URL
url = 'https://www.googleapis.com/calendar/v3/calendars/en.malaysia%23holiday%40group.v.calendar.google.com/events?key='


# AWS resource variables
client_ec2 = boto3.client('ec2')
resource_dynamodb = boto3.resource('dynamodb')
dynamodb_table = resource_dynamodb.Table('public_holidays')

# Date and time variables
time_tz = pytz.timezone(time_zone)
date_today = str(datetime.datetime.now(time_tz).strftime("%Y-%m-%d"))
date_new_year = date(date.today().year, 1, 1)

day_today = str(datetime.datetime.now(time_tz).strftime("%A"))
year = str(datetime.datetime.now(time_tz).strftime("%Y"))
time_now = datetime.datetime.now(time_tz)
shutdown_start = datetime.time(int(shutdown_window[0][:2]), int(shutdown_window[0][3:5]), 00)
shutdown_end = datetime.time(int(shutdown_window[1][:2]), int(shutdown_window[1][3:5]), 00)
time_hour = int(time_now.time().strftime("%H"))
time_min = int(time_now.time().strftime("%M"))
time_now = datetime.time(time_hour, time_min, 00)


# ####----FUNCTIONS BLOCK----#### #

# Check if it as weekend
def compare_day():

    control_var_1 = False
    for day in shutdown_days:
        if str(day) == str(day_today):
            control_var_1 = True
    return control_var_1


# Check if it is shutdown hours
def compare_time():

    if shutdown_start <= shutdown_end:
        return shutdown_start <= time_now <= shutdown_end
    else:
        return shutdown_start <= time_now or time_now <= shutdown_end


# Get EC2 instances with Tag: Management Value: qwerty_auto_schedule.
def ec2_get_instances():

    client_ec2 = boto3.client('ec2')
    instance_list = []

    custom_filter = [{'Name': 'tag:Management', 'Values': ['qwerty_auto_schedule']}, {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]

    response = client_ec2.describe_instances(Filters=custom_filter)

    for reservation in (response["Reservations"]):
        for instance in reservation["Instances"]:
            instance_list.append(instance["InstanceId"])

    return instance_list


# Stop EC2 instances
def ec2_stop_instances():

    client_ec2 = boto3.client('ec2')

    try:
        response = client_ec2.stop_instances(InstanceIds=ec2_get_instances(), DryRun=ec2_dryrun)
        print(response)
    except ClientError as e:
        print(e)


# Start EC2 instances
def ec2_start_intances():

    client_ec2 = boto3.client('ec2')

    try:
        response = client_ec2.start_instances(InstanceIds=ec2_get_instances(), DryRun=ec2_dryrun)
        print(response)
    except ClientError as e:
        print(e)


# Get Google Calendar API
def secret_get():

    secret_name = "google_calendar_api_key"
    region_name = "ap-southeast-1"

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    secret_get_response = client.get_secret_value(SecretId=secret_name)

    calendar_api_key = secret_get_response['SecretString']
    calendar_api_key = json.loads(calendar_api_key)

    return calendar_api_key['google_calendar_api']


# Get MY public holidays from Google Calendar API
def google_calendar_api():

    api_reponse = requests.get(url + secret_get())
    api_response = api_reponse.json()

    response_filter_1 = pyjq.all('.items[] \
        | select(.status | contains("confirmed")) \
        | select(.description != null) \
        | select(((.description | contains("Selangor")) or \
            (.description | contains("Malaysia"))) and \
            select(.start.date | contains($year))) \
        | {start_date: .start.date, end_date: .end.date, summary: .summary}', api_response, vars={"year": year})

    response_filter_2 = pyjq.all('.items[] \
        | select(.status | contains("confirmed")) \
        | select(.description == null) \
        | select(.start.date | contains($year)) \
        | select(.summary | contains("New Year\'s Eve") | not) \
        | select(.summary | contains("Christmas Eve") | not) \
        | select(.summary | contains("Easter Sunday") | not) \
        | select(.summary | contains("Valentine\'s Day") | not) \
        | {start_date: .start.date, end_date: .end.date, summary: .summary}', api_response, vars={"year": year})

    return response_filter_1, response_filter_2


# Delete all items in DynamoDB tables
def dynamodb_delete():
    scan = dynamodb_table.scan()
    with dynamodb_table.batch_writer() as batch:
        for each in scan['Items']:
            batch.delete_item(Key={'start_date': each['start_date']})


# Update DyanmoDB with Google Calendar API response
def dynamodb_update():

    response_filter_1, response_filter_2 = google_calendar_api()

    for holiday in response_filter_1:
        start_date = str(holiday['start_date'])
        end_date = str(holiday['end_date'])
        summary = str(holiday['summary'])

        dynamodb_table.put_item(Item=holiday)


    for holiday in response_filter_2:
        start_date = str(holiday['start_date'])
        end_date = str(holiday['end_date'])
        summary = str(holiday['summary'])

        dynamodb_table.put_item(Item=holiday)


# Check in AWS DynamoDB table if today is a holiday
def compare_holiday_date():

    response = dynamodb_table.get_item(Key={'start_date': date_today})
    check_repsonse = pyjq.all('select(.Item != null)', response)
    if check_repsonse:
        return True


# ####----EXECUTION FUNCTION----#### #

def lambda_handler(event=None, context=None):

    # Check if today is the day to get public holidays
    if day_today == day_to_get_holidays or day_today == date_new_year:
        dynamodb_delete()  # Delete all items in DynamoDB table
        dynamodb_update()  # Query Google Calendar API and update DynamoDB

    # Check if there are instances to shutdown
    if ec2_get_instances():
    # Check if today is not shutdown days
        if compare_day() is not True:

            # Check if it's a holiday
            if compare_holiday_date() is True:
                ec2_stop_instances()  # It's a shutdown day. Shutdown EC2 instances
                # print ("Shutting down instance")
            else:

                # Check if it's shutdown time
                if compare_time() is True:
                    ec2_stop_instances()  # It's within shutdown time. Shutdown EC2 instances
                    # print ("Shutting down instance")
                else:
                    ec2_start_intances()  # It's not within shutdown time. Boot up EC2 instances
                    # print ("Booting up instance")

        else:
            ec2_stop_instances()  # It's a shutdown day. Shutdown EC2 instances
            # print ("Shutting down instance")


lambda_handler()
