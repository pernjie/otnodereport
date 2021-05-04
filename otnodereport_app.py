import requests
import json
import os
import sys
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler


API_ROOT = "https://v5api.othub.info/api"
CONFIG_PATH = './config.json'
INTERVALS = (
    ('years', 60 * 24 * 365),
    ('months', 60 * 24 * 30),
    ('days', 60 * 24),
    ('hours', 60),
    ('minutes', 1)
)
config = None


def main():
    if not os.path.isfile(CONFIG_PATH) or not os.access(CONFIG_PATH, os.R_OK):
        print(f"File config.json missing or not readable!")
        sys.exit()
    
    global config
    config = json.loads(open(CONFIG_PATH, 'r').read())

    # Check required fields
    required_fields = ['nodes', 'report_frequency', 'telegram']
    for field in required_fields:
        if not config.get(field):
            print(f"Missing config field '{field}'")
            sys.exit()

    report_frequency = config['report_frequency']
    days, hours, minutes = report_frequency['days'], report_frequency['hours'], report_frequency['minutes']

    # For longer durations, add some jitter so API server doesn't get congested
    if minutes > 0:
        jitter = 0
    else:
        jitter = 60

    sched = BlockingScheduler()
    sched.add_job(job, 'interval', 
        days=days, 
        hours=hours, 
        minutes=minutes, 
        start_date=config.get('report_start', '2021-01-01 00:00:00'), 
        jitter=jitter
    )
    curr_datetime = datetime.utcnow()
    curr_datetime_str = curr_datetime.strftime("%Y-%m-%d %H:%M:%S")
    print(f'Scheduler started at {curr_datetime_str}.')
    sched.start()


def job():
    report = generate_report()
    result = send_telegram_message(report)


def display_time(minutes):
    """
    Helper function for formatting display of time in minutes to something like:
    2 hours 15 minutes
    """
    result = []

    for name, count in INTERVALS:
        value = minutes // count
        if value:
            minutes -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    return ', '.join(result)


def call_othub_api(url):
    """
    Helper function to call OTHub API
    """
    try:
        print(f'Calling URL: {url}')
        resp = requests.get(url)
        if resp.status_code == 200:
            response_data = json.loads(resp.text)
            return response_data
        else:
            raise OtHubAPIError
    except:
        raise OtHubAPIError


class OtHubAPIError(Exception):
    pass
    
    
def get_recent_jobs(node_id, prev_datetime):
    """
    Return jobs from node after a certain timestamp
    :param node_id: Node ID to fetch jobs of
    :param prev_datetime: Timestamp that jobs should be after
    """
    pagination_limit = 10
    page = 1
    recent_jobs = []
    
    # Loop until no more relevant jobs found
    while (True):
        url = f'{API_ROOT}/nodes/DataHolder/{node_id}/jobs?_sort=FinalizedTimestamp&_order=DESC&_limit={pagination_limit}&_page={page}'
        
        try:
            jobs_data = call_othub_api(url)
        except OtHubAPIError:
            print(f'Unable to fetch jobs data for {node_id}')
            break

        # Return if no more jobs
        if len(jobs_data) == 0:
            break

        job_before_prev_datetime = False

        for job in jobs_data:
            # Sample format: 2021-05-01T08:00:00
            job_start = job['FinalizedTimestamp']
            job_start = datetime.strptime(job_start, "%Y-%m-%dT%H:%M:%S")
            job_status = job['Status']

            # Keep job if after the required timestamp
            # Else loop can be exited since jobs are fetched in reverse chronological order
            if job_start > prev_datetime:
                recent_jobs.append(job)
            else:
                job_before_prev_datetime = True
                break

        if job_before_prev_datetime:
            break

        page += 1

        # Handle any weird cases causing infinite loop
        if page > 1000:
            print("Too many loops!")
            break
        
    return recent_jobs


def report_overview():
    """
    Generate the overview text portion for report
    """
    total_staked = 0
    total_locked = 0
    num_nodes = 0
    
    for node in config['nodes']:
        node_id = node['node_id']
        url = f'{API_ROOT}/nodes/DataHolder/{node_id}'
        try:
            node_data = call_othub_api(url)
        except OtHubAPIError:
            print(f'Unable to fetch overview data for {node_id}')
            break

        staked_tokens = float(node_data['StakeTokens'])
        locked_tokens = float(node_data['StakeReservedTokens'])
        
        total_staked += staked_tokens
        total_locked += locked_tokens
        num_nodes += 1
    
    overview_str = ""
    overview_str += f"Total Nodes: {num_nodes}\nTotal Staked: {total_staked}\nTotal Locked: {total_locked}"
    
    return overview_str
    

def report_jobs(curr_datetime):
    """
    Generate the jobs text portion for report
    """
    frequency = config['report_frequency']
    frequency_days, frequency_hours, frequency_mins = frequency['days'], frequency['hours'], frequency['minutes']

    if frequency_mins <= 0 and frequency_hours <= 0 and frequency_days <= 0:
        print("Invalid frequency!")
        return
    
    # Calculate timestamp for filtering jobs to be after
    prev_datetime = curr_datetime - timedelta(
        days=frequency_days, 
        hours=frequency_hours, 
        minutes=frequency_mins
    )

    # Formatting strings
    prev_datetime_str = prev_datetime.strftime("%Y-%m-%d %H:%M:%S")
    frequency_display = display_time(frequency_days * 60 * 24 + frequency_hours * 60 + frequency_mins)
    
    print(f'Searching for jobs after {prev_datetime_str} ({frequency_display} ago)..\n')
    
    all_recent_jobs = []
    jobs_str = ""
    
    # Check for jobs one node at a time
    for node in config['nodes']:
        node_name = node['node_name']
        node_id = node['node_id']
        recent_jobs = get_recent_jobs(node_id, prev_datetime)

        # Save node name into job metadata as well for display purposes
        for recent_job in recent_jobs:
            recent_job['NodeName'] = node_name
        all_recent_jobs.extend(recent_jobs)
    
    # Creating report text
    report_str = ""
    
    if len(all_recent_jobs) == 0:
        report_str += f'No new jobs since {prev_datetime_str} ({frequency_display} ago)'
    elif len(all_recent_jobs) == 1:
        report_str += f'1 new job since {prev_datetime_str} ({frequency_display} ago)\n\n'
    else:
        report_str += f'{len(all_recent_jobs)} new jobs since {prev_datetime_str} ({frequency_display} ago)\n'
    
    if len(all_recent_jobs) > 0:
        report_str += "----------------------------------------------"
        for recent_job in all_recent_jobs:
            offer_id = recent_job['OfferId']
            node_name = recent_job['NodeName']
            job_start = recent_job['FinalizedTimestamp']
            job_start = datetime.strptime(job_start, "%Y-%m-%dT%H:%M:%S")
            token_amount = recent_job['TokenAmountPerHolder']
            holding_time = recent_job['HoldingTimeInMinutes']
            holding_time = display_time(holding_time)
            report_str += f'\nOffer {offer_id}\nNode: {node_name}\nToken Amount: {token_amount}\nHolding Time: {holding_time}\n'
        report_str += "----------------------------------------------"
    
    return report_str


def generate_report():
    """
    Combines the text portions of report into one
    """
    curr_datetime = datetime.utcnow()
    curr_datetime_str = curr_datetime.strftime("%Y-%m-%d %H:%M:%S")
    report_str = f"Report for {curr_datetime_str}\n\n"
    
    report_str += report_overview()
    report_str += "\n\n"
    report_str += report_jobs(curr_datetime)
    
    return report_str


def send_telegram_message(message):
    """
    Helper function to send telegram message
    """
    telegram_config = config['telegram']
    bot_token, chat_id = telegram_config['bot_token'], telegram_config['chat_id']
    send_text = f'https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&parse_mode=Markdown&text={message}'
    response = requests.get(send_text)

    return response.json()


if __name__ == "__main__":
    main()
