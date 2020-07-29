# Custom Designed AWS Instance Scheduler

## Purpose
We can use AWS Instance Scheduler to stop and start your instances based on a schedule. Here is the [link](https://aws.amazon.com/premiumsupport/knowledge-center/stop-start-instance-scheduler/) to the guide from AWS to configure AWS Instance Scheduler.

However I wanted to extend this solution further. I want to shutdown all our AWS EC2 test instances not only after office hours and weekends, but also during Malaysia Public Holidays.

## Tools

|                 |    Tools   |                     |
|:---------------:|:----------:|:-------------------:|
| AWS Eventbridge | AWS Lambda |  AWS Lambda Layers  |
|  Amazon Linux 2 | Python 3.7 |     Python3 Pip     |
|   AWS DynamoDB  |   AWS IAM  | Google Calendar API |

## Flowchart
![Custom Instance Scheduler Flowchart](https://github.com/hadriane/custom_designed_aws_instance_scheduler/blob/master/images/aws_instance_scheduler.jpg)

## Steps
1. **Google Calendar API**
    1. Login to your [Google Developer Console](https://console.developers.google.com/)
    2. Click on **New Project**
    3. Give it a **Project Name**
    4. Click **Create**
    5. Now click on **Credentials**
    6. Click **CREATE CREDENTIALS**
    7. Click **API Key**
    8. Save the API key somewhere safe
    9. Click **Restrict Key**
    10. Select **Google Calendar API**

2. **AWS Secrets Manager**
    1. Go to AWS Secrets Manager
    2. Click **Store a new secret**
    3. Select **Other type of secrets**
    4. For **Key** enter google_calendar_api_key
    5. For **Value** enter the Google Calendar API Key from step 1
    6. Click **Next**
    7. Enter google_calendar_api_key for **Secret name**
    8. Click **Next**
    9. Note down the ARN for this resource

3. **AWS DynamoDB**
    1. Go to AWS DynamoDB
    2. Click **Create table**
    3. Give it a **Table name** public_holidays
    4. The **Primary key** should be start_date and type string
    5. Click **Create**
    6. Note down the ARN for this resource

4. **AWS IAM**
    1. Go to AWS IAM
    2. Click on **Polices**
    3. Click **Create policy**
    4. Click on the **JSON** tab
    5. Enter the following JSON policy
    ```json
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "logs:CreateLogGroup",
                "Resource": "arn:aws:logs:ap-southeast-1:XXXXXXXXXXXX:*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    "arn:aws:logs:ap-southeast-1:XXXXXXXXXXXX:log-group:/aws/lambda/test:*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetResourcePolicy",
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                    "secretsmanager:ListSecretVersionIds"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:ap-southeast-1:XXXXXXXXXXXX:secret:google_calendar_api_key-XXXXXX"
                ]
            },
            {
                "Sid": "ListAndDescribe",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:List*",
                    "dynamodb:DescribeReservedCapacity*",
                    "dynamodb:DescribeLimits",
                    "dynamodb:DescribeTimeToLive"
                ],
                "Resource": "*"
            },
            {
                "Sid": "SpecificTable",
                "Effect": "Allow",
                "Action": [
                    "dynamodb:BatchGet*",
                    "dynamodb:DescribeStream",
                    "dynamodb:DescribeTable",
                    "dynamodb:Get*",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchWrite*",
                    "dynamodb:CreateTable",
                    "dynamodb:Delete*",
                    "dynamodb:Update*",
                    "dynamodb:PutItem"
                ],
                "Resource": "arn:aws:dynamodb:ap-southeast-1:XXXXXXXXXXXX:table/public_holidays"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:StartInstances",
                    "ec2:StopInstances"
                ],
                "Resource": "arn:aws:ec2:*:*:instance/*",
                "Condition": {
                    "StringEquals": {
                        "ec2:ResourceTag/Management": "qwerty_auto_schedule"
                    }
                }
            },
            {
                "Effect": "Allow",
                "Action": "ec2:DescribeInstances",
                "Resource": "*"
            }
        ]
    }
    ```
    6. Click **Review policy**
    7. Give it a **Name** ***ex:*** instance_scheduler
    8. Click **Create policy**
    9. Now go to **Roles**
    10. Click **Create role**
    11. Select Lambda for **Choose a use case**
    12. Click **Next: Permissions**
    13. Select the instance_scheduler role created before
    14. Click **Next: Tags**
    15. Give it Tags if you want then click **Next: Review**
    16. Give it a **Role name** ***ex:*** instance_scheduler
    17. Click **Create role**

> For Step 5, it is better to use an Amazon Linux 2 AMI to avoid errors in following steps

5. **AWS Lambda Layer**
    1. Preparing Lambda Layer
        1. Go to AWS EC
        2. Click on **Launch Instance**
        3. Select Amazon Linux 2 AMI
        4. Proceed through the Launch instance configuration
        5. SSH into the the instance
        6. Run the following commands
        ```bash
        sudo yum -y groupinstall "Development Tools"
        sudo yum -y install python3-devel
        sudo yum -y install python34
        cd /tmp
        mkdir python && cd python
        pip install pyjq, pytz, requests -t ./
        zip -r /tmp/labmda_layer.zip python
        ```
        7. Download labmda_layer.zip file to your PC/Mac
        8. Go to AWS Lambda
        9. Click on **Layers**
        10. Give the Layer a **Name** ***ex:*** instance_scheduler
        11. Give the Layer a **Description** ***ex:*** instance_scheduler
        12. Upload labmda_layer.zip to the Layer
        13. Select Python 3.7 as the **Compatible runtimes**
        14. Click **Create**

6. **AWS Lambda**
    1. Go to AWS Lambda
    2. Click **Create function**
    3. Select **Author from scratch**
    4. Give it a **Function name** ***ex:*** instance_scheduler
    5. Select **Runtime** as Python 3.7
    6. Choose the role we created in step 4 in **Choose or create an execution role**
    7. Click **Create function**
    8. Click on **Layers**
    9. Click **Add a layer**
    10. Select the layer created in step 5
    11. Click **Add**
    12. Paste the code from aws_instance_scheduler.py.j2 here
    13. Click **Save**

7. **AWS Eventbridge**
    1. Go to AWS Eventbridge
    2. Click **Create rule**
    3. Give it an **Name** ***ex:*** instance_scheduler
    4. Select Schedule for **Define pattern**
    5. Select **Fixed rate every** and enter 1 for **hours**
    6. Let **Target** be Lambda function
    7. Select the function instance_scheduler
    8. Give it Tags if you want then click **Create**
