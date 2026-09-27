import shlex
from typing import List, Dict, Any, Callable, Optional

class CommandParserError(Exception):
    """Base class for all command parser exceptions."""
    pass

class CommandNotFoundError(CommandParserError):
    """Raised when a command is not recognized."""
    pass

class MissingArgumentError(CommandParserError):
    """Raised when a required argument is missing."""
    def __init__(self, command: 'Command', arg_name: str):
        self.command = command
        self.arg_name = arg_name
        super().__init__(f"Error: Usage: '{command.get_usage()}'")

class ExtraArgumentsError(CommandParserError):
    """Raised when extra arguments are provided to a command."""
    def __init__(self, command: 'Command', extra_tokens: List[str]):
        self.command = command
        self.extra_tokens = extra_tokens
        super().__init__(f"Error: Usage: '{command.get_usage()}'")

class Argument:
    """Represents a command argument."""
    def __init__(self, name: str, required: bool = True, is_vararg: bool = False):
        self.name = name
        self.required = required
        self.is_vararg = is_vararg

class Command:
    """Represents a command or subcommand, supporting builder pattern configuration."""
    def __init__(self, name: str, parent: Optional['Command'] = None):
        self.name = name
        self.parent = parent
        self.subcommands: Dict[str, 'Command'] = {}
        self._callback: Optional[Callable] = None
        self.arguments: List[Argument] = []
        self._usage: Optional[str] = None
        self._description: Optional[str] = None
        self._case_insensitive: Optional[bool] = None

    def case_insensitive(self, val: bool) -> 'Command':
        """Overrides the case-insensitive parsing behavior for this specific command/subcommand."""
        self._case_insensitive = val
        return self

    def callback(self, cb: Callable) -> 'Command':
        """Sets the execution callback for this command."""
        self._callback = cb
        return self

    def argument(self, name: str, required: bool = True, is_vararg: bool = False) -> 'Command':
        """Adds a positional or vararg argument to the command."""
        if self.arguments and not self.arguments[-1].required and required and not is_vararg:
            raise ValueError("Cannot have a required argument after an optional one.")
        if self.arguments and self.arguments[-1].is_vararg:
            raise ValueError("Cannot add arguments after a variadic argument.")
        self.arguments.append(Argument(name, required, is_vararg))
        return self

    def subcommand(self, name: str) -> 'Command':
        """Adds or retrieves a subcommand."""
        if name in self.subcommands:
            return self.subcommands[name]
        sub = Command(name, parent=self)
        self.subcommands[name] = sub
        return sub

    def usage(self, text: str) -> 'Command':
        """Sets a custom usage string for error output."""
        self._usage = text
        return self

    def description(self, text: str) -> 'Command':
        """Sets the description for the command/subcommand (used in help)."""
        self._description = text
        return self

    def get_usage(self) -> str:
        """Returns the usage string, generating one if not explicitly set."""
        if self._usage:
            return self._usage
        parts = []
        curr = self
        while curr:
            parts.insert(0, curr.name)
            curr = curr.parent
        for arg in self.arguments:
            if arg.is_vararg:
                parts.append(f"<{arg.name}...>")
            elif arg.required:
                parts.append(f"<{arg.name}>")
            else:
                parts.append(f"[{arg.name}]")
        return " ".join(parts)

class CommandParser:
    """Main parser that routes input tokens to registered Commands."""
    def __init__(self, description: str = "Available Robot Chat Console Commands:", add_help: bool = True, case_insensitive: bool = True):
        self.description = description
        self.commands: Dict[str, Command] = {}
        self.case_insensitive = case_insensitive
        if add_help:
            self.command("help").description("Display this help message.")

    def format_help(self) -> str:
        """Generates a formatted help message detailing all commands with descriptions."""
        lines = []
        if self.description:
            lines.append(self.description)
        
        def collect_commands(cmd: Command):
            if cmd._description:
                lines.append(f"  {cmd.get_usage().ljust(33)} - {cmd._description}")
            for sub in cmd.subcommands.values():
                collect_commands(sub)
                
        for cmd in self.commands.values():
            collect_commands(cmd)
            
        return "\n".join(lines)

    def command(self, name: str) -> Command:
        """Creates or retrieves a root command."""
        if name in self.commands:
            return self.commands[name]
        cmd = Command(name)
        self.commands[name] = cmd
        return cmd

    def _find_command(self, commands: Dict[str, Command], token: str) -> Optional[Command]:
        """Looks up a token in a commands dict using either case-sensitive or case-insensitive matching."""
        for cmd in commands.values():
            is_ci = cmd._case_insensitive if cmd._case_insensitive is not None else self.case_insensitive
            if is_ci:
                if token.lower() == cmd.name.lower():
                    return cmd
            else:
                if token == cmd.name:
                    return cmd
        return None

    def parse(self, command_text: str) -> tuple[Command, Dict[str, Any]]:
        """Parses command_text and returns the matched Command and its arguments."""
        try:
            tokens = shlex.split(command_text)
        except ValueError:
            tokens = command_text.split()

        if not tokens:
            raise CommandNotFoundError("No command provided.")
        
        cmd_name = tokens[0]
        matched_cmd = self._find_command(self.commands, cmd_name)
        if not matched_cmd:
            raise CommandNotFoundError(f"Error: Unknown command '{cmd_name}'. Type 'help' for available commands.")
            
        current_cmd = matched_cmd
        token_idx = 1
        
        # Traverse subcommands
        while token_idx < len(tokens):
            next_token = tokens[token_idx]
            matched_sub = self._find_command(current_cmd.subcommands, next_token)
            if matched_sub:
                current_cmd = matched_sub
                token_idx += 1
            else:
                break
                
        # Parse arguments starting from token_idx
        parsed_args = {}
        
        args_tokens = tokens[token_idx:]
        arg_idx = 0
        token_arg_idx = 0
        
        while arg_idx < len(current_cmd.arguments):
            arg_def = current_cmd.arguments[arg_idx]
            
            if arg_def.is_vararg:
                parsed_args[arg_def.name] = args_tokens[token_arg_idx:]
                token_arg_idx = len(args_tokens)
                arg_idx += 1
                break
                
            if token_arg_idx < len(args_tokens):
                parsed_args[arg_def.name] = args_tokens[token_arg_idx]
                token_arg_idx += 1
            else:
                if arg_def.required:
                    raise MissingArgumentError(current_cmd, arg_def.name)
                else:
                    parsed_args[arg_def.name] = None
            arg_idx += 1
            
        if token_arg_idx < len(args_tokens):
            raise ExtraArgumentsError(current_cmd, args_tokens[token_arg_idx:])
            
        return current_cmd, parsed_args
