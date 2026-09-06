# Task 2 - BMI Calculator

## Objective
A Python command-line tool that calculates a user's Body Mass Index (BMI) and classifies it into standard health categories.

## Tech Stack
- Python 3
- Built-in libraries only (no external packages needed)

## Features
- Prompts user for weight (kg) and height (m)
- Calculates BMI using the formula: `BMI = weight / (height ** 2)`
- Classifies result into: Underweight, Normal, Overweight, Obese
- Displays BMI rounded to 2 decimal places
- Input validation: rejects non-numeric and negative/zero values with clear error messages
- Colored terminal output for better readability
- Visual BMI scale bar showing where your result falls
- Personalized health tip based on category
- Session history: shows all BMI calculations done in the current run

## How to Run
```bash
python3 bmi_calculator.py
```
Then follow the on-screen prompts to enter your weight and height.

## Example Output
