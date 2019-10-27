import utils
import discord_logging
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

import static
from classes.enums import ReturnType
from database import Base
from database.UtcDateTime import UtcDateTime


log = discord_logging.get_logger()


other_bot = "There is currently another bot called u/kzreminderbot that is duplicating the functionality of this bot. " \
			"Since it replies to the same RemindMe! trigger phrase, you may receive a second message from it with the " \
			f"same reminder. If this is annoying to you, please click [this link](" \
			f"{utils.build_message_link('kzreminderbot', 'Feedback! KZ Reminder Bot')}) to send feedback to that bot " \
			f"author and ask him to use a different trigger."


class Reminder(Base):
	__tablename__ = 'reminders'

	id = Column(Integer, primary_key=True)
	source = Column(String(400), nullable=False)
	message = Column(String(500))
	user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
	requested_date = Column(UtcDateTime, nullable=False)
	target_date = Column(UtcDateTime, nullable=False)
	recurrence = Column(String(500))
	defaulted = Column(Boolean, nullable=False)

	comment = relationship("DbComment", cascade="all")
	user = relationship("User")

	def __init__(
		self,
		source,
		message,
		user,
		requested_date,
		target_date,
		defaulted=False
	):
		self.source = source
		self.message = message
		self.user = user
		self.requested_date = requested_date
		self.target_date = target_date
		self.defaulted = defaulted

	@staticmethod
	def build_reminder(
		source,
		message,
		user,
		requested_date,
		time_string
	):
		result_message = None
		defaulted = False
		if time_string is not None:
			target_date = utils.parse_time(time_string, requested_date, user.timezone)

			if target_date is None:
				result_message = f"Could not parse date: \"{time_string.strip()}\", defaulting to one day"
				log.info(result_message)
				target_date = utils.parse_time("1 day", requested_date, None)

			elif target_date < requested_date:
				result_message = f"This time, {time_string.strip()}, was interpreted as " \
					f"{utils.get_datetime_string(target_date)}, which is in the past"
				log.info(result_message)
				return None, result_message

		else:
			result_message = "Could not find a time in message, defaulting to one day"
			log.info(result_message)
			defaulted = True
			target_date = utils.parse_time("1 day", requested_date, None)

		reminder = Reminder(
			source=source,
			message=message,
			user=user,
			requested_date=requested_date,
			target_date=target_date,
			defaulted=defaulted
		)

		return reminder, result_message

	def __str__(self):
		return f"{utils.get_datetime_string(self.requested_date)} " \
			f": {utils.get_datetime_string(self.target_date)} : {self.user.name} " \
			f": {self.source} : {self.message}"

	def render_message_confirmation(self, result_message, comment_return=None):
		bldr = utils.str_bldr()
		if result_message is not None:
			bldr.append(result_message)
			bldr.append("\n\n")
		bldr.append("I will be messaging you on ")
		bldr.append(utils.render_time(self.target_date, self.user.timezone))
		bldr.append(" to remind you")
		if self.message is None:
			bldr.append(" of [**this link**](")
			bldr.append(self.source)
			bldr.append(")")
		else:
			bldr.append(": ")
			bldr.append(self.message)

		if comment_return is not None and comment_return in (
			ReturnType.FORBIDDEN,
			ReturnType.THREAD_LOCKED,
			ReturnType.DELETED_COMMENT,
			ReturnType.RATELIMIT,
			ReturnType.THREAD_REPLIED
		):
			bldr.append("\n\n")
			bldr.append("I'm sending this to you as a message instead of replying to your comment because ")
			if comment_return == ReturnType.FORBIDDEN:
				bldr.append("I'm not allowed to reply in this subreddit.")
			elif comment_return == ReturnType.THREAD_LOCKED:
				bldr.append("the thread is locked.")
			elif comment_return == ReturnType.DELETED_COMMENT:
				bldr.append("it was deleted before I could get to it.")
			elif comment_return == ReturnType.RATELIMIT:
				bldr.append("I'm new to this subreddit and have already replied to another thread here recently.")
			elif comment_return == ReturnType.THREAD_REPLIED:
				bldr.append("I've already replied to another comment in this thread.")

		bldr.append("\n\n")
		bldr.append(other_bot)

		return bldr

	def render_comment_confirmation(self, thread_id, count_duplicates=0):
		bldr = utils.str_bldr()

		if self.defaulted:
			bldr.append("**Defaulted to one day.**\n\n")

		if self.user.timezone is not None:
			bldr.append(f"Your default time zone is set to `{self.user.timezone}`. ")

		bldr.append("I will be messaging you on ")
		bldr.append(utils.render_time(self.target_date, self.user.timezone))
		bldr.append(" to remind you of [**this link**](")
		bldr.append(utils.replace_np(self.source))
		bldr.append(")")

		bldr.append("\n\n")

		bldr.append("[**")
		if count_duplicates > 0:
			bldr.append(str(count_duplicates))
			bldr.append(" OTHERS CLICKED")
		else:
			bldr.append("CLICK")
		bldr.append(" THIS LINK**](")
		bldr.append(utils.build_message_link(
			static.ACCOUNT_NAME,
			"Reminder",
			f"[{self.source}]\n\n{static.TRIGGER}! "
			f"{utils.get_datetime_string(self.target_date, format_string='%Y-%m-%d %H:%M:%S %Z')}"
		))
		bldr.append(") to send a PM to also be reminded and to reduce spam.")

		if thread_id is not None:
			bldr.append("\n\n")
			bldr.append("^(Parent commenter can ) [^(delete this message to hide from others.)](")
			bldr.append(utils.build_message_link(
				static.ACCOUNT_NAME,
				"Delete Comment",
				f"Delete! {thread_id}"
			))
			bldr.append(")")

		bldr.append("\n\n")
		bldr.append(other_bot)

		return bldr

	def render_notification(self):
		bldr = utils.str_bldr()

		bldr.append("RemindMeBot reminder here!")
		bldr.append("\n\n")

		if self.message is not None:
			bldr.append("I'm here to remind you:\n\n> ")
			bldr.append(self.message)
			bldr.append("\n\n")

		bldr.append("The source comment or message:\n\n>")
		bldr.append(self.source)
		bldr.append("\n\n")

		if self.requested_date is None:
			bldr.append("This reminder was created before I started saving the creation date of reminders.")
		else:
			bldr.append("You requested this reminder on: ")
			bldr.append(utils.render_time(self.requested_date, self.user.timezone))
		bldr.append("\n\n")

		bldr.append("[Click here](")
		bldr.append(utils.build_message_link(
			static.ACCOUNT_NAME,
			"Reminder",
			f"[{self.message}]\n\n{static.TRIGGER}! "
		))
		bldr.append(") and set the time after the ")
		bldr.append(static.TRIGGER)
		bldr.append(" command to be reminded of the original comment again.")

		bldr.append("\n\n")
		bldr.append(other_bot)

		return bldr
