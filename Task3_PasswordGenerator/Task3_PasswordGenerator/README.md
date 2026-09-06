# Task 3 - Random Password Generator

## Objective
A Python command-line tool that generates strong, random passwords based on user-defined criteria.

## Tech Stack
- Python 3
- `random` and `string` modules (built-in)

## Features
- Prompts user to specify desired password length (minimum 8 characters enforced)
- Prompts user to choose character types: uppercase, lowercase, numbers, symbols (at least 2 types must be selected)
- Generates a password guaranteed to include at least one character from each selected type
- Input validation: rejects invalid lengths and insufficient type selection with clear error messages
- Option to generate another password without restarting the program
- Colored terminal output for readability

## How to Run
```bash
python3 password_generator.py
```
Then follow the prompts to set your desired length and character types.

## Example Output
```
Enter desired password length (min 8): 12

Choose character types to include (enter y/n for each):
  Include uppercase letters (A-Z)? (y/n): y
  Include lowercase letters (a-z)? (y/n): y
  Include numbers (0-9)? (y/n): y
  Include symbols (!@#$...)? (y/n): n

--- Generated Password ---
wJ7oikx1Zg75
```

## Author
Submitted as part of the Oasis Infobyte Python Programming Internship (OIBSIP).
