# OT Node Reporting
This is a simple script meant to generate scheduled summary reports on your OriginTrail nodes, and deliver this report via a Telegram bot. A sample report looks like this:

```
Report for 2021-05-02 05:00:00

Total Nodes: 3
Total Staked: 15000.0
Total Locked: 162.21478723138057

2 new jobs since 2021-05-01 05:00:00 (1 day ago)
----------------------------------------------
Offer 0xabcde1234ef2e6b090c123456adadad981c1b9ad627fd805398d957d7871234a
Node: Node 1
Job Start: 2021-05-01 08:45:00
Token Amount: 2.194208044077156900
Holding Time: 3 months

Offer 0xabcde1234ef2e6b090c123456adadad981c1b9ad627fd805398d957d7875432b
Node: Node 3
Job Start: 2021-05-02 03:00:00
Token Amount: 5.961739048334433000
Holding Time: 5 years
----------------------------------------------
```
All data is obtained from OT Hub's API v5. 

## Installation
Note: You can run this project anywhere you want, it does not necessarily have to be a node server, since the APIs can be called from anywhere. You only need to run one instance of it. 

1) Clone this project into your root directory (or wherever you want).
```
cd /root/
git clone https://github.com/pernjie/otnodereport.git
```

2) Create your config file based on the sample provided
```
cd otnodereport
cp sample_config.json config.json
nano config.json
```
The mandatory fields `nodes`, `report_frequency`, and `telegram` should be self-explanatory. Fill them in accordingly and save.

You may also choose to add the following optional fields:
Field  | Type | Default | Description
------ | ---- | ------- | -----------
`gmt_offset` | number |0 | GMT offset to converts all timestamps to for display purposes
`report_start` | string | 2021-01-01 00:00:00 | To specify when the scheduled intervals start, useful for if you want daily reports to come in at a certain time of the day
`skip_jobless_notification` | bool | false | If set to true, you will not receive a notification if the nodes didn't score any new jobs

3) Install required libraries. If your server doesn't have Python (minimally Python 3.8) or pip, you will have to install them as well. If you are using the Digital Ocean server, it should come with Python by default. 
```
pip3 install -r requirements.txt
```

4) Set up the script to run in the background. For my Digital Ocean server, my preferred way is to set up a systemd service as follows, but feel free to use any other method (eg. tmux, screen, nohup). 

```
nano /etc/systemd/system/otnodereport.service
```

Paste this (change the path of working directory and Python environment as needed) and save.
```
[Unit]
Description=OT Node Report

[Service]
WorkingDirectory=/root/otnodereport/
ExecStart=/usr/bin/python3 -u otnodereport_app.py

[Install]
WantedBy=default.target
```

Start the service.
```
sudo systemctl restart otnodereport.service
```

Tail the service logs and make sure there was no error when running it.
```
journalctl -u otnodereport.service -f
```

To stop the service:
```
sudo systemctl stop otnodereport.service
```

If you made any config changes, be sure to restart the service again.
```
sudo systemctl restart otnodereport.service
```
