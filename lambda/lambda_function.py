"""
    Description: This sample demonstrates handling intents from an Alexa skill using the Alexa Skills Kit SDK for Python.
                 Please visit https://alexa.design/cookbook for additional examples on implementing slots, dialog management,
                 session persistence, api calls, and more. This sample is built using the handler classes approach in skill builder.
                 When testing, you may need to delete or reset the user’s birthday. To do this, say: "Alexa, tell Cake Time I was 
                 born on {month} {day} {year}."
         Author: Mr. Bloom
           Date: Feb 6 2022
           Refs: https://developer.amazon.com/en-US/alexa/alexa-skills-kit/get-deeper/tutorials-code-samples/build-a-multimodal-alexa-skill
                 https://www.youtube.com/watch?v=84d8c8_LJM0&t=380s
                 https://developer.amazon.com/en-US/docs/alexa/alexa-presentation-language/apl-document.html
                 https://developer.amazon.com/en-US/docs/alexa/alexa-presentation-language/apl-interface.html#renderdocument-directive
        
"""

# -*- coding: utf-8 -*-

#----------------------------------------------------------------------------------------------#
#------------------------------------------  IMPORTS ------------------------------------------#
#----------------------------------------------------------------------------------------------#
import logging
import ask_sdk_core.utils as ask_utils
import os
import requests
import calendar
from datetime import datetime

# The pytz library allows accurate and cross platform timezone calculations, and will help us figure out the user's timezone accurately.
from pytz import timezone

# Import the S3 Persistence adapter, create your S3 adapter and set you up with a bucket on S3 to store your data.
# An Amazon S3 bucket is a public cloud storage resource. A bucket is similar to a file folder for storing objects,
# which consists of data and descriptive metadata. This new dependency will allow you to use the AttributesManager
# to save and read user data using Amazon S3.
from ask_sdk_s3.adapter import S3Adapter
s3_adapter = S3Adapter(bucket_name=os.environ["S3_PERSISTENCE_BUCKET"])
from ask_sdk_core.skill_builder import CustomSkillBuilder

from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput

# Remember that we must only send our display information to a device
# with a display, so we must check for this. The check for a display
# is provided in ask_sdk_core.utils.
from ask_sdk_core.utils import get_supported_interfaces

from ask_sdk_model import Response

#----------------------------------------------------------------------------------------------#
#--------------------------------------  HELPER FUNCTIONS -------------------------------------#
#----------------------------------------------------------------------------------------------#

# We also need to read our apl_template.json and apl_assets.json files
# We’ll use “ _load_apl_document“ function and the json library.
import json
def _load_apl_document(file_path):
    """ load the APL json document at the path into a dict object """
    with open(file_path) as infile:
        return json.load(infile)

# To use the add_directive, we need to import some more code.
# We only need the RenderDocumentDirective buut the others come free.
from ask_sdk_model.interfaces.alexa.presentation.apl import (
	    RenderDocumentDirective, ExecuteCommandsDirective, SpeakItemCommand,
	    AutoPageCommand, HighlightMode)

#----------------------------------------------------------------------------------------------#
#--------------------------------------  GLOBAL VARIABLES -------------------------------------#
#----------------------------------------------------------------------------------------------#
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#----------------------------------------------------------------------------------------------#
#--------------------------------------- CUSTOM INTENTS  --------------------------------------#
#----------------------------------------------------------------------------------------------#
class LaunchRequestHandler(AbstractRequestHandler):
    """ Handler for Skill Launch """

    def can_handle(self, handler_input):
        """ The can_handle() function is where you define what requests the handler responds to. 
            If your skill receives a request, the can_handle() function within each handler 
            determines whether or not that handler can service the request. In this case, the 
            user wants to launch the skill, which is a LaunchRequest. Therefore, the can_handle()
            function within the LaunchRequestHandler will let the SDK know it can fulfill the 
            request. In computer terms, the can_handle returns true to confirm it can do the work. """
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        """ The handle() function returns a response to the user. 
            The handlerInput.responseBuilder piece of the SDK will help build the response to the user.
            Calling the .speak() function tells responseBuilder to speak the value of speak_output to the user.
            Calling the .ask() function tells responseBuilder to listen for the user's response, rather than simply exiting. 
            It also allows you to specify a way to ask the question to the user again, if they don't respond.
            If you just want the skill to speak and then exit, you would omit this line of code. 
            When you've finished building the response and are ready to send it to the user's device, use 
            .response to conver the responseBuilder’s work into the response that the skill will return.
        """

        # Set speak_output string (alexa's verbal response) and ask follow-up question
        speak_output = "Hello! This is Cake Time. What is your birthday?"
        
        # The reprompt should provide more context to help the user provide an answer 
        reprompt_text = "I was born Nov. 6th, 2014. When were you born?"
        
        # Add APL visuals to your response with a render directive (for devices with an LCD screen). 
        # This directive takes the form of Alexa.Presentation.APL.RenderDocument. 
        # You can add a directive using the SDK easily by calling handlerInput.responseBuilder.addDirective({…​})
        display_directive = RenderDocumentDirective(
                                token="pagerToken",
                                document=_load_apl_document("launchDocument.json"),
                                datasources=_load_apl_document("launchDataSources.json")
                            )

        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.ask(reprompt_text)
        
        # Even though you can add a render directive to every response, not all devices can react to this. 
        # In order to safely respond with the Alexa.Presentation.APL.RenderDocument, you must first make 
        # sure the calling device sends the proper request object. This "if" statement is going to check
        # if the APL interface is sent in the request envelope. Only then, do we want to add the response. 
        if get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
            handler_input.response_builder.add_directive(display_directive)

        return handler_input.response_builder.response

#----------------------------------------------------------------------------------------------#
class HasBirthdayLaunchRequestHandler(AbstractRequestHandler):
    """ Handler for launch after they have set their birthday.
        The canHandle() function checks if the user's birthday information is saved in Amazon S3.
        If it is, the handler lets the SDK know it can do the work (it has the user's birthday 
        information and can do what comes next). The handle() function tells Alexa to say, 
        'Welcome back. It looks like there are x more days until your y-th birthday.'
    """

    def can_handle(self, handler_input):
        """ Read the data stored in Amazon S3 before asking the user for their birthday.
            If the data exists, the skill doesn’t need to ask for it. 
            If the data isn’t there, it will ask for the information.
        """
        # Extract persistent attributes and check if they are all present
        attr = handler_input.attributes_manager.persistent_attributes
        attributes_are_present = ("year" in attr and "month" in attr and "day" in attr)
        return attributes_are_present and ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        attr = handler_input.attributes_manager.persistent_attributes
        year = int(attr['year'])
        month = attr['month']       # month is a string, and we need to convert it to a month index later
        day = int(attr['day'])

        #------------ Use the settings API to get current date and then compute how many days until user’s bday -------#
        #
        #   We can use the Alexa Settings API to return the time zone that our customer’s device is set to. Then,
        #   we can use that to make our date calculations totally accurate and avoid the embarrassing situation
        #   where we wish them a happy birthday too soon or too late. To make use of the Alexa Settings API, we'll
        #   need to pass the device’s ID via a web request. The web request will return the time zone as a string to our skill.

        # The device ID is provided in every request that comes to the skill code. 
        # We will traverse the request object to get the device ID using the requestEnvelope:
        sys_object = handler_input.request_envelope.context.system
        device_id = sys_object.device.device_id

        # get Alexa Settings API information
        api_endpoint = sys_object.api_endpoint
        api_access_token = sys_object.api_access_token

        # Now that we have the Device ID, API endpoint, and the access token, we are ready to call the Alexa Settings API
        # to get the user time zone. Construct systems api timezone url (pass device ID to getSystemTimeZone function).
        url = '{api_endpoint}/v2/devices/{device_id}/settings/System.timeZone'.format(api_endpoint=api_endpoint, device_id=device_id)
        headers = {'Authorization': 'Bearer ' + api_access_token}

        # There’s a chance that an error can happen when the code makes a call to the Alexa Settings API. 
        # For example, if the API takes too long to respond, the code could time out. Therefore, you need to wrap the code in a try_catch__ block.
        userTimeZone = ""
        
        # In the try block, to get the time zone. 
        try:
            r = requests.get(url, headers=headers)
            res = r.json()
            logger.info("Device API result: {}".format(str(res)))
            userTimeZone = res
        
        # The catch block will log an error message using console.log and return an error message response that Alexa will say to the user.
        except Exception:
            handler_input.response_builder.speak("There was a problem connecting to the service")
            return handler_input.response_builder.response

        # Getting the current date with the time according to the time zone captured from the user's device
        now_time = datetime.now(timezone(userTimeZone))

        # Removing the time from the date because it affects our difference calculation
        now_date = datetime(now_time.year, now_time.month, now_time.day)
        current_year = now_time.year

        # Getting the next birthday: convert month string to month index and combine the year and month of their birthday with the current year.
        month_as_index = list(calendar.month_abbr).index(month[:3].title())
        next_birthday = datetime(current_year, month_as_index, day)

        #------------ Say happy birthday on the user’s birthday -----------------#

        # Determine if the user's birthday has already passed this calendar year. 
        # If it has, add a year to the value of their next birthday.
        if now_date > next_birthday:
            next_birthday = datetime(
                current_year + 1,
                month_as_index,
                day
            )
            current_year += 1
        
        # Setting the default speak_output to Happy xth Birthday!!
        age = str(current_year - year)
        if age[-1] == '1': 
            ordinal = "st"
        elif age[-1] == '2':
            ordinal = "nd"
        elif age[-1] == '3':
            ordinal = "rd"
        else:
            ordinal = "th"
        
        # Assume today is the user's birthday and wish them a Happy Birthday!
        speak_output = "Happy {}{} birthday!".format(age, ordinal)
        display_directive = RenderDocumentDirective(
                                token="pagerToken",
                                document=_load_apl_document("launchDocument.json"),
                                datasources=_load_apl_document("hasBirthdayDataSources.json")
                            )

        # However, if today is not their birthday, alter speak output and display directive
        if now_date != next_birthday:
            
            # Convert each date into Unix epoch time (the number of seconds elapsed since 00:00:00 January 1, 1970), and then
            # calculate the difference in milliseconds between the two dates and take the absolute value of the difference. 
            diff_days = abs((now_date - next_birthday).days)
            
            # Adjust grammar (singular or plural) depending on the number of days 
            speak_output = "Welcome back. It looks like there are {days} days until your {birthday_num}{suffix} birthday".format(
                                days=diff_days,
                                birthday_num=age,
                                suffix=ordinal
                            )
            if diff_days == 1:
                speak_output = speak_output.replace("are", "is")
                speak_output = speak_output.replace("days", "day")
            
            display_directive = RenderDocumentDirective(
                                    token="pagerToken",
                                    document=_load_apl_document("launchDocument.json"),
                                    datasources=_load_apl_document("birthdayCountdownDataSources.json")
                                )
                                
        handler_input.response_builder.speak(speak_output)

        # Check for a display and add the directive if there is one.
        if get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
            handler_input.response_builder.add_directive(display_directive)

        return handler_input.response_builder.response

#----------------------------------------------------------------------------------------------#
class CaptureBirthdayIntentHandler(AbstractRequestHandler):
    """ Handler for Capture Birthday Intent """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return ask_utils.is_intent_name("CaptureBirthdayIntent")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """

        # The Cake Time skill code receives the year, month, and day. 
        # Create three variables in the handler to save the slots the skill is collecting.
        slots = handler_input.request_envelope.request.intent.slots
        year = slots["year"].value
        month = slots["month"].value
        day = slots["day"].value
        
        # Now, tell Amazon S3 to save these values so the skill won't forget their birthday.
        # The SDK provides a useful mechanism for saving information across sessions: the AttributesManager.
        # The code tells the AttributesManager what the data is, and the manager sends it to Amazon S3.
        # With the manager, the skill can read the data from session to session and your read/write code
        # can remain the same, even if you change where you save your data later.
        attributes_manager = handler_input.attributes_manager
        
        # This piece of code is mapping the variables already declared in the code to corresponding variables
        # that will be created in Amazon S3 when the code runs. These variables are now declared as persistent
        # (they are local to the function in which they are declared, yet their values are retained in memory
        # between calls to the function). Now you can save the user's data to them. 
        birthday_attributes = {
            "year": year,
            "month": month,
            "day": day
        }
        
       # Use the AttributesManager to set the data to save to Amazon S3.
        attributes_manager.persistent_attributes = birthday_attributes
        attributes_manager.save_persistent_attributes()
        
        # Update the logic within the handler so the skill will confirm to the user that their birthday
        # was heard correctly. In this case, you will have Alexa read the birthday back to the user.
        speak_output = 'Thanks, I will remember that you were born {month} {day} {year}.'.format(month=month, day=day, year=year)
        
        display_directive = RenderDocumentDirective(
                                token="pagerToken",
                                document=_load_apl_document("launchDocument.json"),
                                datasources=_load_apl_document("captureBirthdayDataSources.json")
                            )

        handler_input.response_builder.speak(speak_output)

        # Check for a display and add the directive if there is one.
        if get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
            handler_input.response_builder.add_directive(display_directive)

        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
#-------------------------------------- BUILT-IN INTENTS  -------------------------------------#
#----------------------------------------------------------------------------------------------#
class HelpIntentHandler(AbstractRequestHandler):
    """ Handler for Help Intent """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return ask_utils.is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        speak_output = "If you accidentally entered the wrong birthday, you can change it by saying, \
                        'Alexa, tell Cake Time I was born on, and then say the month day and year of your birthday."
        reprompt_text = "I was born Nov. 6th, 2014. When were you born?"
        display_directive = RenderDocumentDirective(
                                token="pagerToken",
                                document=_load_apl_document("launchDocument.json"),
                                datasources=_load_apl_document("captureBirthdayDataSources.json")
                            )

        handler_input.response_builder.speak(speak_output)
        handler_input.response_builder.ask(reprompt_text)
        if get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
            handler_input.response_builder.add_directive(display_directive)

        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
class CancelOrStopIntentHandler(AbstractRequestHandler):
    """ Single handler for Cancel and Stop Intent """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        speak_output = "later dude!"
        # reprompt_text = ""
        display_directive = RenderDocumentDirective(
                                token="pagerToken",
                                document=_load_apl_document("launchDocument.json"),
                                datasources=_load_apl_document("sessionEndDataSources.json")
                            )

        handler_input.response_builder.speak(speak_output)
        # handler_input.response_builder.ask(reprompt_text)
        if get_supported_interfaces(handler_input).alexa_presentation_apl is not None:
            handler_input.response_builder.add_directive(display_directive)
            
        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
class FallbackIntentHandler(AbstractRequestHandler):
    """ Single handler for Fallback Intent """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return ask_utils.is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        logger.info("In FallbackIntentHandler")
        speak_output = "Hmm, I'm not sure. You can say Hello or Help. What would you like to do?"
        reprompt_text = "I didn't catch that. What can I help you with?"
        # display_directive = {}

        handler_input.response_builder.speak(speak_output)
        # handler_input.response_builder.ask(reprompt_text)
        # handler_input.response_builder.add_directive(display_directive)
        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
class SessionEndedRequestHandler(AbstractRequestHandler):
    """ Handler for Session End """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return ask_utils.is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        #
        # Any cleanup logic
        # goes here.
        #
        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
class IntentReflectorHandler(AbstractRequestHandler):
    """
    The intent reflector is used for interaction model testing and debugging.
    It will simply repeat the intent the user said. You can create custom handlers
    for your intents by defining them above, then also adding them to the request
    handler chain below.
    """

    def can_handle(self, handler_input):
        """ type: (HandlerInput) -> bool """
        return ask_utils.is_request_type("IntentRequest")(handler_input)

    def handle(self, handler_input):
        """ type: (HandlerInput) -> Response """
        intent_name = ask_utils.get_intent_name(handler_input)
        speak_output = "You just triggered " + intent_name + "."
        # reprompt_text = ""
        # display_directive = {}

        handler_input.response_builder.speak(speak_output)
        # handler_input.response_builder.ask(reprompt_text)
        # handler_input.response_builder.add_directive(display_directive)
        return handler_input.response_builder.response

#----------------------------------------------------------------------------------------------#
class CatchAllExceptionHandler(AbstractExceptionHandler):
    """
    Generic error handling to capture any syntax or routing errors. If you receive an error
    stating the request handler chain is not found, you have not implemented a handler for
    the intent being invoked or included it in the skill builder below.
    """

    def can_handle(self, handler_input, exception):
        """ type: (HandlerInput, Exception) -> bool """
        return True

    def handle(self, handler_input, exception):
        """ type: (HandlerInput, Exception) -> Response """
        logger.error(exception, exc_info=True)

        speak_output = "Sorry, I had trouble doing what you asked. Please try again."
        # reprompt_text = ""
        # display_directive = {}

        handler_input.response_builder.speak(speak_output)
        # handler_input.response_builder.ask(reprompt_text)
        # handler_input.response_builder.add_directive(display_directive)
        return handler_input.response_builder.response


#----------------------------------------------------------------------------------------------#
#-------------------------------- SKILL BUILDER / APP ROUTING  --------------------------------#
#----------------------------------------------------------------------------------------------#

# The SkillBuilder object acts as the entry point for your skill, routing all request and response
# payloads to the handlers above.
sb = CustomSkillBuilder(persistence_adapter=s3_adapter)

# Make sure any new handlers or interceptors you've defined are included below.
# The order matters - they're processed top to bottom. Also make sure to put
# IntentReflectorHandler last, so it doesn't override your custom intent handlers.
sb.add_request_handler(HasBirthdayLaunchRequestHandler())
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(CaptureBirthdayIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_request_handler(IntentReflectorHandler())

# Exception Handlers
sb.add_exception_handler(CatchAllExceptionHandler())

# Lambda Handler
lambda_handler = sb.lambda_handler()
