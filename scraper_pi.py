from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time, os, re, pprint, ast
from deepdiff import DeepDiff
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

cwd = os.getcwd()

VERSION = '1.0.0'

PREV_BOOKINGS = '/bookings/previous_bookings.txt'
LATEST_BOOKINGS = '/bookings/latest_bookings.txt'
LATEST_DIFFS = '/bookings/latest_differences.txt'

MAILING_LIST = ['ollie.f.wells@gmail.com']

class PadelBot(webdriver.Chrome):
    def __init__(self, service, options):
        super().__init__(service=service, options=options)

    def get_date(self):
        self.implicitly_wait(5)
        time.sleep(5)
        date_element = self.find_element(By.ID, 'picker_daily')
        time.sleep(5)
        date = date_element.text
        return date

    def next_date(self):
        self.implicitly_wait(5)
        print("Clicking next date...")
        time.sleep(10)
        try:
            self.find_element(By.CLASS_NAME, 'ti-angle-right').click()
        except StaleReferenceException as e:
            print("Error: {e}; \n waiting another 10secs...")
            time.sleep(10)
            self.find_element(By.CLASS_NAME, 'ti-angle-right').click()

    def get_slots(self):
        time.sleep(5)
        self.implicitly_wait(5)        
        grid = {}
        slots = self.find_elements(By.CLASS_NAME, 'slot')
        for slot in slots:
            slot_raw = slot.get_attribute('data-original-title')
            slot_data = list(re.split('<br>', slot_raw))
            
            if len(slot_data) > 1:  # Removing "Time passed" slots
                court = slot_data[1].replace('\n', '').replace('\r', '').strip()
                status = slot_data[0].replace('\n', '').replace('\r', '').strip()
                booking_time = slot_data[2].replace('\n', '').replace('\r', '').strip()
                
                if court not in grid:
                    grid[court] = {}
                if status not in grid[court]:
                    grid[court][status] = []
                grid[court][status].append(booking_time)
        return grid

    def get_bookings(self):
        time.sleep(5)
        bookings = {}
        # For the next 7 days
        for i in range(0,7):
            self.next_date()
            date = self.get_date()
            print(f"Getting bookings for {date}...")
            grid = self.get_slots()
            bookings[date] = grid
        return bookings

def get_differences(bookings):
    with open(f'{cwd}{LATEST_BOOKINGS}', 'r') as file:
        data = file.read()
    latest_bookings = ast.literal_eval(data)

    differences = DeepDiff(latest_bookings, bookings)

    return differences

def overwrite_prev_bookings():
    print("Overwriting previous bookings...")
    if os.path.exists(f'{cwd}{PREV_BOOKINGS}'):
        os.remove(f'{cwd}{PREV_BOOKINGS}')

    os.rename(f'{cwd}{LATEST_BOOKINGS}', f'{cwd}{PREV_BOOKINGS}')

def write_latest_bookings(bookings):
    print("Writing latest bookings...")
    with open(f'{cwd}{LATEST_BOOKINGS}', 'w') as file:
        pprint.pprint(bookings, file)
            
def analyse_differences(diffs):
    favourites = {
        "Monday": ['18:00 - 19:00', '19:00 - 20:00'],
        "Tuesday": ['18:00 - 19:00', '19:00 - 20:00'],
        "Wednesday": ['18:00 - 19:00', '19:00 - 20:00'],
        "Thursday": ['18:00 - 19:00', '19:00 - 20:00'],
        "Friday": ['18:00 - 19:00', '19:00 - 20:00'],
        "Saturday": ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '15:00 - 16:00', '16:00 - 17:00', '17:00 - 18:00'],
        "Sunday": ['08:00 - 09:00', '09:00 - 10:00', '10:00 - 11:00', '11:00 - 12:00', '12:00 - 13:00', '13:00 - 14:00', '14:00 - 15:00', '15:00 - 16:00', '16:00 - 17:00', '17:00 - 18:00']
    }
    useful_diffs = []
    other_diffs = []
    report = {}
    try:
        for key, value in diffs['iterable_item_added'].items():
            # Extracting the day out of the key
            status = list(re.split(r'[\[\]]', str(key)))[5].replace("'", '').replace('"', '')
            day = list(re.split(r'[\[\]]', str(key)))[1].split(' ')[0].replace("'", '').replace('"', '')
            date = list(re.split(r'[\[\]]', str(key)))[1].replace("'", '').replace('"', '')
            time = value
            if status == 'Available':
                if time in favourites[day]:
                    useful_diffs.append({date:time})
                else:
                    other_diffs.append({date:time})
    except:
        pass
    report['favourites'] = useful_diffs
    report['other'] = other_diffs
    
    return report

def send_email(bookings):
    print("Sending email...")
    print(bookings)
    server = smtplib.SMTP('smtp-mail.outlook.com', 587)
    server.starttls()
    server.login('ofwpython@hotmail.com', 'SPloge01')

    msg = MIMEMultipart('related')
    
    with open(f'{cwd}/report_email.html', 'rb') as f:
        email_body = f.read().decode('UTF-8')

    for k,v in email_params.items():
        email_body = email_body.replace(k,str(v))
    
    html_text = MIMEText(email_body, 'html')
    msg.attach(html_text)

    msg['Bcc'] = ", ".join(MAILING_LIST)
    msg['Subject'] = "New Padel Slots"
    msg['From'] = 'ofwpython@hotmail.com'

    server.send_message(msg)

    print("...email sent")

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument('--headless')  # Run headless Chrome (no GUI)
chrome_options.add_argument('window-size=1920,1080') # Ensure window sees the browser booking grid and not the mobile version
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

# Create a new instance of the Chrome driver
service = Service('/usr/bin/chromedriver')
bot = PadelBot(service=service, options=chrome_options)

try:
    # URL of the website to be scraped
    url = "https://www.matchi.se/facilities/g4pthepadelyard"

    # Open the webpage
    bot.get(url)

    # Get the bookings
    bookings = bot.get_bookings()

    # Identify differences
    differences = get_differences(bookings)

    # Write results
    if differences:
        print("Writing differences... ")
        with open(f'{cwd}{LATEST_DIFFS}', 'w') as file:
            pprint.pprint(differences, file)
        
        overwrite_prev_bookings()

        write_latest_bookings(bookings)

        report = analyse_differences(differences)
        
        email_params = {'{version}': VERSION,
                            '{favourites}':report['favourites'],
                            '{other}': report['other'],
                            '{error}':''
                            }

        if len(report['favourites']) > 0:
            print("** New Favourite Slots **")
            pprint.pprint(report['favourites'])

            print("** Other New Slots **")
            pprint.pprint(report['other'])

            send_email(email_params)

        elif len(report['other']) > 0:
            print("** Other New Slots **")
            pprint.pprint(report['other'])

            send_email(email_params)
        else:
            print("No new slots")
    else:
        print("No differences")
        


finally:
    # Close the browser
    bot.quit()
    
    email_params = {'{version}': VERSION,
                            '{favourites}':"cron_working",
                            '{other}': "hello from cron",
                            '{error}':''
                            }
    send_email(email_params)
