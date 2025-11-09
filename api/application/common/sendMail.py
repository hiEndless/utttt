import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
import logging


class MailSender:
    def __init__(self):
        self.email_pool = [
            {'email': 'service@apeyesai.com', 'password': 'EslaGefUqEdZ2T3g'},
            {'email': 'service_01@apeyesai.com', 'password': '3abP8bek6nxKhn00'},
            # 添加更多邮箱账号
        ]
        self.email_index = 0
        self.email_counter = 0
        logging.basicConfig(level=logging.INFO)

    def _switch_email_account(self):
        self.email_index = (self.email_index + 1) % len(self.email_pool)
        self.email_counter = 0
        logging.info(f'切换发信邮箱为：{self.email_pool[self.email_index]["email"]}')

    def send_email(self, sender_name, receiver_emails, subject, body, is_html=True, attachment_path=None):
        # 获取当前邮箱账号
        sender_email = self.email_pool[self.email_index]['email']
        sender_password = self.email_pool[self.email_index]['password']

        # 更新计数器
        self.email_counter += 1

        # 每发送100封邮件切换邮箱账号
        if self.email_counter >= 100:
            self._switch_email_account()

        # 创建MIMEMultipart对象
        msg = MIMEMultipart()
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = ', '.join(receiver_emails)
        msg['Subject'] = subject

        # 根据is_html标志设置正文格式
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))

        # 如果有附件
        if attachment_path:
            with open(attachment_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f"attachment; filename= {attachment_path}")
                msg.attach(part)

        # 连接到SMTP服务器并发送邮件
        try:
            server = smtplib.SMTP('smtp.feishu.cn', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            for email in receiver_emails:
                try:
                    server.sendmail(sender_email, email, text)
                    logging.info(f"邮件发送成功：{email}")
                except Exception as e:
                    logging.error(f"邮件发送失败：{email}, 错误：{e}")
                    self._switch_email_account()
            server.quit()
            logging.info("邮件发送成功！")
        except Exception as e:
            logging.error(f"邮件发送失败: {e}")
            self._switch_email_account()


if __name__ == '__main__':
    mail_sender = MailSender()

    code  = '123456'
    body = f"""
                <!doctype html>
                <html>
                    <head>
                        <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
                    </head>
                    <body>
                        <div>
                            <p>您好，您的邮箱验证码：{code}</p>
                            <p>请在5分钟内完成验证。</p>
                            <p>如果您没有进行此操作，请忽略此邮件。</p>
                        </div>
                    </body>
                </html>
                """
    mail_sender.send_email("APEYES AI", subscribers, f'邮箱验证[k.apeyesai.com]', body)
