import os
import logging
import smtplib

logger = logging.getLogger(__name__)


def send_email(recipient, subject, body, user='irrigation.computer.amnon@gmail.com', pwd=None):
	if pwd is None:
		if 'IRRIGATOR_EMAIL_PASSWORD' in os.environ:
			pwd = os.environ['IRRIGATOR_EMAIL_PASSWORD']
		else:
			logger.warning('IRRIGATOR_EMAIL_PASSWORD not in environment variables. please set.')
			return False

	gmail_user = user
	gmail_pwd = pwd
	FROM = user
	TO = recipient if type(recipient) is list else [recipient]
	SUBJECT = subject
	TEXT = body

	# Prepare actual message
	message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (FROM, ", ".join(TO), SUBJECT, TEXT)
	try:
		server = smtplib.SMTP("smtp.gmail.com", 587)
		server.ehlo()
		server.starttls()
		server.login(gmail_user, gmail_pwd)
		server.sendmail(FROM, TO, message)
		server.close()
		logger.info('sent email: subject %s to %s' % (SUBJECT, TO))
		return True
	except Exception as err:
		logger.warning('failed to send email: subject %s to %s. error %s' % (SUBJECT, TO, err))
		return False
