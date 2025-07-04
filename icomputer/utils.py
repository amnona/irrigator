import os
import logging
import smtplib

logger = logging.getLogger(None)


def send_email(recipient, subject, body, user='irrigation.computer.amnon@gmail.com', pwd=None, smtp_server='smtp-relay.sendinblue.com', smtp_port=587, smtp_user='sugaroops@yahoo.com'):
	'''this is for the sendinblue smtp email server
		for gmail use:
		smtp_server='smtp.gmail.com'
	'''
	if pwd is None:
		if 'IRRIGATOR_EMAIL_PASSWORD' in os.environ:
			pwd = os.environ['IRRIGATOR_EMAIL_PASSWORD']
		else:
			logger.warning('IRRIGATOR_EMAIL_PASSWORD not in environment variables. please set.')
			return False
	if smtp_server is None:
		if 'IRRIGATOR_EMAIL_SMTP_SERVER' in os.environ:
			pwd = os.environ['IRRIGATOR_EMAIL_SMTP_SERVER']
		else:
			logger.warning('IRRIGATOR_EMAIL_SMTP_SERVER not in environment variables. please set.')
			return False
	if smtp_user is None:
		if 'IRRIGATOR_EMAIL_SMTP_USER' in os.environ:
			pwd = os.environ['IRRIGATOR_EMAIL_SMTP_USER']
		else:
			logger.warning('IRRIGATOR_EMAIL_SMTP_USER not in environment variables. please set.')
			return False

	FROM = user
	TO = recipient if type(recipient) is list else [recipient]
	SUBJECT = subject
	TEXT = body

	# Prepare actual message
	message = """From: %s\nTo: %s\nSubject: %s\n\n%s""" % (FROM, ", ".join(TO), SUBJECT, TEXT)
	logger.info('prepared email message: %s' % message)
	try:
		logger.info('connecting to email server %s on port %d' % (smtp_server, smtp_port))
		server = smtplib.SMTP(smtp_server, smtp_port)
		server.ehlo()
		server.starttls()
		logger.info('logging in to email server %s as user %s with password %s' % (smtp_server, smtp_user, pwd))
		server.login(smtp_user, pwd)
		server.sendmail(FROM, TO, message)
		server.close()
		logger.info('sent email: subject %s to %s' % (SUBJECT, TO))
		return True
	except Exception as err:
		logger.warning('failed to send email: subject %s to %s. error %s' % (SUBJECT, TO, err))
		return False
