import subprocess
import time
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email():
    sender_email = "minamijogen@outlook.com"
    receiver_email = "nansyukugen@gmail.com"
    password = "20020201nsy"
    smtp_server = "smtp-mail.outlook.com"
    port = 587

    message = MIMEMultipart("alternative")
    message["Subject"] = "Service Process Ended"
    message["From"] = sender_email
    message["To"] = receiver_email

    text = """\
    The Process Ended!
    Failed to restart it.
    """
    part = MIMEText(text, "plain")
    message.attach(part)

    server = SMTP(smtp_server, port)
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, message.as_string())
    server.quit()

def check_process():
    # 使用grep -v grep来排除当前grep进程
    command = ['ps', 'aux']
    grep = ['grep', 'gunicorn']
    grep_v = ['grep', '-v', 'grep']

    # 启动ps aux和两次grep
    process_ps = subprocess.Popen(command, stdout=subprocess.PIPE)
    process_grep = subprocess.Popen(grep, stdin=process_ps.stdout, stdout=subprocess.PIPE)
    process_ps.stdout.close()  # 允许ps的stdout通过管道连接到grep
    output_grep = subprocess.Popen(grep_v, stdin=process_grep.stdout, stdout=subprocess.PIPE)
    process_grep.stdout.close()  # 允许grep的stdout通过管道连接到grep -v

    output = output_grep.stdout.read().decode('utf-8')

    if not output:
        send_email()
        print("Email sent and exiting.")
        exit()

if __name__ == "__main__":
    while True:
        check_process()
        time.sleep(60)