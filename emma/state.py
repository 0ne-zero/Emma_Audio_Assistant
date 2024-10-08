from abc import ABC, abstractmethod
import ast
from os import getenv, lseek
import re
from shutil import ExecError
from subprocess import getoutput
from time import tzname
from playsound import playsound
from hashlib import sha256
from colorama import Fore, Style

from emma.utilities import upper_first_letter
from emma.operation import *
INITIATED = False


def all_states():
    parsed = ast.parse(open(__file__).read())
    # all operations are class
    classes = [c for c in parsed.body if isinstance(c, ast.ClassDef)]
    operations_class = []
    for c in classes:
        if c.bases[0].id == "IState":
            operations_class.append(
                globals()[c.name]()
            )
    return operations_class



class IState(ABC):
    _context = None    
    @abstractmethod
    def _input_processing(self) -> IOperation:
        pass

    @abstractmethod
    def processing(self, context):
        pass

 
    @abstractmethod
    def _perform_processing(self, op) -> None:
        pass

    @abstractmethod
    def _state_in_checker(self, input) -> bool:
        '''
        Checks state should change to this state(self) or not
        This method call by _check_state_change in every processing
        '''

    def _state_out_checker(self):
        if self._get_context().input['text'].strip() == '':
            return None
        states = self._get_context().get_global_var("__all_states")
        for s in states:
            # if state is itself pass it
            if type(s).__name__ == self.__class__.__name__:
                continue
            if s._state_in_checker(self._get_context().input['text']):
                return s
        return None

    @abstractmethod
    def _get_input(self):
        pass

    def _check_state_change(self):
        return self._state_out_checker()

    def _set_context(self, context):
        self._context = context

    def _get_context(self):
        return self._context

    def _set_state(self, state):
        self._get_context().state = state

    def _change_state(self, state):
        # Get previous state name
        self._get_context().previous_state_name = type(self._get_context().state).__name__
        # Change state of context (Emma)
        self._set_state(state)
        # Output text
        self._get_context().output[
            'text'] = f"State changed form {self._get_context().previous_state_name} to {type(state).__name__}"
        self._output_processing()
        self._after_processing()

    def _output_processing(self):
        '''
        This method by default just prints output in screen
        This can be overrided by subclasses
        '''
        self._get_context().print_output()

    def _after_processing(self):
        '''Doing some work after operation processing(clean up,logging,etc...)'''

        # Logging Informations
        msg = f"\nInput: {self._get_context().input['text']}\nOutput: {self._get_context().output['text']}"
        if not self._get_context().log(msg, 'DEBUG'):
            raise ExecError("Error during logging")

        # Clean up
        self._get_context().input['text'] = ''
        self._get_context().input['lang'] = self._get_context().speak_lang


class TextState(IState):
    def processing(self, context):
        '''
        Processing ready mode stuff.
        This method needs self.input['text'] as input, so that variable should been fill.
        '''
        # Set context
        self._set_context(context)
        # Get input
        self._get_input()

        # Check state change
        state = self._check_state_change()
        if state != None:
            self._change_state(state)
            return

        # Input processing ----- select appropriate
        op = self._input_processing(
            self._get_context().input['text'])

        # Wait for check internet connection done at least, one time
        # while self._get_context().infity_loop_worked == False:
        #    pass

        # Perform selected operation
        self._perform_processing(op)

        # Output processing
        self._output_processing()

        # Cleaning and logging,etc
        self._after_processing()

    def _get_input(self):
        if self._get_context().input['text'] == '':
            self._get_context().input['text'] = input("You: ")

    def _input_processing(self, input) -> IOperation:
        '''Processing input and detect operation'''
        # For on all operations, and call its checker
        for op in self._get_context().get_global_var("__all_operations"):

            if op == AIMLResponse:
                continue
            if op.checker(input):
                return op
        return AIMLResponse

    def _perform_processing(self, op: IOperation):
        '''Perform an operation'''

        # if operation needs internet connection, and system hasn't connection so should tell user
        if hasattr(op, "need_internet"):
            if op.need_internet == True and self._get_context().get_global_var("__internet_connection") == False:
                self._get_context().output['text'] = "This operation require internet connection, If you would like to do this operation, please connect to the internet."
                return

        # perform operation
        # create a instance
        o = op()
        # call input extractor from operation
        if hasattr(op, "need_input") and op.need_input == True:
            o.input_extractor(self._get_context().input['text'])

        # do the action
        if hasattr(op,"need_core") and op.need_core == True:
            self._get_context().output['text'] = o.action(self._get_context())
        else:
            self._get_context().output['text'] = o.action()

    def _state_in_checker(self, input) -> bool:
        '''this class doesn't need to check because it's default state in every processing'''
        text_state_in_keywords = (
            'text state mode', 'go to text state mode', 'go to text state', 'text state', 'text mode')
        for item in text_state_in_keywords:
            if input == item:
                return True
        return False


class HalfAudioState(IState):
    '''Retruns output with playing it in speaker but inputs gets in text mode'''

    def processing(self, context):
        # Set context
        self._set_context(context)
        # Get input
        self._get_input()

        # Check state change
        state = self._check_state_change()
        if state != None:
            self._change_state(state)
            return
        # Input processing ----- select appropriate
        op = self._input_processing(
            self._get_context().input['text'])

        # Wait for check internet connection done at least, one time
        # while self._get_context().infity_loop_worked == False:
        #    pass

        # Perform selected operation
        self._perform_processing(op)

        # Output processing
        self._output_processing()

        # Cleaning and logging,etc
        self._after_processing()

    def _get_input(self):
        if self._get_context().input['text'] == '':
            self._get_context().input['text'] = input("You: ")

    def _input_processing(self, input) -> IOperation:
        '''Processing input and detect operation'''
        # For on all operations, and call its checker
        for op in self._get_context().get_global_var("__all_operations"):

            if op == AIMLResponse:
                continue
            if op.checker(input):
                return op
        else:
            return AIMLResponse

    def _perform_processing(self, op) -> None:
        '''Perform an operation'''

        # if operation needs internet connection, and system hasn't connection so should tell user
        if hasattr(op, "need_internet"):
            if op.need_internet == True and self._get_context().get_global_var("__internet_connection") == False:
                self._get_context().output['text'] = "This operation require internet connection, If you would like to do this operation, please connect to the internet."
                return

        # perform operation
        # create a instance
        o = op()
        # call input extractor from operation
        if hasattr(op, "need_input") and op.need_input == True:
            o.input_extractor(self._get_context().input['text'])

        # do the action
        if hasattr(op,'need_core') and op.need_core == True:
            self._get_context().output['text'] = o.action(self._context)
        else:
            self._get_context().output['text'] = o.action()

    def _state_in_checker(self, input) -> bool:
        half_audio_state_in_keywords = (
            'half audio state', 'go to half audio state', 'half audio mode', 'go to half audio mode')
        for item in half_audio_state_in_keywords:
            if input == item:
                return True
        return False

    # Override output processing method
    def _output_processing(self):
        '''Print output in screen and also say it'''
        # Print output in screen
        super()._output_processing()
        # Play output in speaker
        self._get_context().say_output()


class AudioState(IState):
    '''Input taken from microphone and output plays in speaker (cmd state is always in text mode)'''

    def processing(self, context):
        # Set context
        self._set_context(context)
        # Get input
        self._get_input()

        # Check state change
        state = self._check_state_change()
        if state != None:
            self._change_state(state)
            return
        # Input processing ----- select appropriate
        op = self._input_processing(
            self._get_context().input['text'])

        # Wait for check internet connection done at least, one time
        # while self._get_context().infity_loop_worked == False:
        #    pass

        # Perform selected operation
        self._perform_processing(op)

        # Output processing
        self._output_processing()

        # Cleaning and logging,etc
        self._after_processing()

    def _get_input(self):
        if self._get_context().input['text'] == '':
            self._get_context().input['text'], self._get_context().input['lang'] = self._get_context().listen()

    def _input_processing(self) -> IOperation:
        '''Processing input and detect operation'''
        # For on all operations, and call its checker
        for op in self._get_context().get_global_var("__all_operations"):

            if op == AIMLResponse:
                continue
            if op.checker(input):
                return op
        else:
            return AIMLResponse

    def _perform_processing(self, op) -> None:
        '''Perform an operation'''

        # if operation needs internet connection, and system hasn't connection so should tell user
        if hasattr(op, "need_internet"):
            if op.need_internet == True and self._get_context().get_global_var("__internet_connection") == False:
                self._get_context().output['text'] = "This operation require internet connection, If you would like to do this operation, please connect to the internet."
                return

        # perform operation
        # create a instance
        o = op()
        # call input extractor from operation
        if hasattr(op, "need_input") and op.need_input == True:
            o.input_extractor(self._get_context().input['text'])

        # do the action
        if hasattr(op,'need_core') and op.need_core == True:
            self._get_context().output['text'] = o.action(self._context)
        else:
            self._get_context().output['text'] = o.action()

    def _state_in_checker(self, input) -> bool:
        audio_state_in_keywords = (
            'audio mode', 'go to audio mode', 'audio state', 'go to audio state')
        for item in audio_state_in_keywords:
            if input == item:
                return True
        return False

    # Override output processing method
    def _output_processing(self):
        super()._output_processing()
        self._get_context().say_output()


class CMDState(IState):
    def processing(self, context):
        '''Processing command mode stuff'''
        # Set context
        self._set_context(context)
        # Get input
        self._get_input()

        # Check state change
        state = self._check_state_change()
        if state != None:
            self._change_state(state)
            return
        # Input processing
        op = self._input_processing(self._get_context().input['text'])

        # Perform cmd operation (run command in shell)
        self._perform_processing(op)

        # Output processing
        self._output_processing()

        # Cleaning and logging,etc
        self._after_processing()

    def _input_processing(self, input) -> IOperation:
        return Cmd

    def _get_input(self):
        if self._get_context().input['text'] == '':
            # Get PS1 environment variable
            ps1 = getenv("PS1")
            if ps1 == None:
                # Get user name and device name and current directory (pwd)
                user_name = getoutput('whoami')
                device_name = getoutput('hostname')
                pwd = getoutput('pwd')
                # Colored shell symbols and in the end of string reset color to normal
                ps1 = f"{Fore.LIGHTGREEN_EX}{user_name}@{device_name}:{Fore.LIGHTBLUE_EX}{pwd}{Style.RESET_ALL}$ "

            self._get_context().input['text'] = input(ps1)

    def _perform_processing(self, op) -> None:
        # Create instance of cmd operation
        o = op()
        # Call input_extractor of operation
        o.input_extractor(self._get_context().input['text'])
        # Do the action (run input in shell and put it into output)
        self._get_context().output['text'] = o.action()

    def _state_in_checker(self, input) -> bool:
        cmd_state_checker_keywords = (
            'cmd mode', 'command line mode', 'go to cmd mode', 'go cmd',
            'go command line', 'cmd state', 'command line staet',
            'go to cmd state', 'go to command line state',)
        for item in cmd_state_checker_keywords:
            if input == item:
                return True

        return False


class StopState(IState):
    def processing(self, context):
        # Set context
        self._set_context(context)
        # Get input
        self._get_input()

        # Check state change
        state = self._check_state_change()
        if state != None:
            self._change_state(state)
            return

        # Display to user that change the state
        op  = self._input_processing()
        self._perform_processing(op)
        self._output_processing()
        self._after_processing() 

    def _input_processing(self) -> IOperation:
        return IamStopped

    def _perform_processing(self,op) -> None:
        o = op()
        self._get_context().output['text'] = o.action()

    def _state_in_checker(self, input) -> bool:
        stop_state_keywords = (
            'stop yourself', 'stop', 'kill yourself','stop mode','stop state'
        )
        for item in stop_state_keywords:
            if input == item:
                return True
        return False

    def _get_input(self):
        if self._get_context().input['text'] == '':
            if self._get_context().previous_state_name == "AudioState":
                self._get_context().input['text'] = self._get_context().listen()
            else:
                self._get_context().input['text']= input("You: ")