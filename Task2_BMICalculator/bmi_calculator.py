"""
BMI Calculator (Beginner Tier - Command Line) - Creative Edition
------------------------------------------------------------------
Prompts the user for weight (kg) and height (m), calculates BMI,
classifies it, validates input, and adds some visual flair:
colored output, a BMI scale bar, health tips, and session history.
"""

# ANSI color codes for terminal styling
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"


CATEGORY_INFO = {
    "Underweight": {
        "color": Colors.BLUE,
        "emoji": "📉",
        "tip": "Consider a nutrient-rich diet with more calories and consult a doctor if needed.",
    },
    "Normal": {
        "color": Colors.GREEN,
        "emoji": "✅",
        "tip": "Great job! Keep up a balanced diet and regular exercise.",
    },
    "Overweight": {
        "color": Colors.YELLOW,
        "emoji": "⚠️",
        "tip": "Try incorporating more physical activity and mindful eating into your routine.",
    },
    "Obese": {
        "color": Colors.RED,
        "emoji": "🚨",
        "tip": "Consider consulting a healthcare provider for a personalized health plan.",
    },
}

# Session history (not persisted to disk, just for this run)
history = []


def print_banner():
    print(Colors.CYAN + Colors.BOLD + "=" * 46)
    print("        🧮  BMI CALCULATOR  🧮")
    print("=" * 46 + Colors.RESET)


def get_positive_float(prompt):
    """
    Keeps asking the user for input until they provide a valid
    positive number. Rejects non-numeric and negative/zero values.
    """
    while True:
        raw_value = input(Colors.CYAN + prompt + Colors.RESET).strip()
        try:
            value = float(raw_value)
        except ValueError:
            print(Colors.RED + "  -> Invalid input. Please enter a numeric value (e.g. 65.5)." + Colors.RESET)
            continue

        if value <= 0:
            print(Colors.RED + "  -> Invalid input. Value must be greater than zero." + Colors.RESET)
            continue

        return value


def calculate_bmi(weight_kg, height_m):
    """BMI = weight (kg) / height (m) squared"""
    return weight_kg / (height_m ** 2)


def classify_bmi(bmi):
    """Classifies BMI into standard health categories."""
    if bmi < 18.5:
        return "Underweight"
    elif bmi < 25:
        return "Normal"
    elif bmi < 30:
        return "Overweight"
    else:
        return "Obese"


def draw_bmi_scale(bmi):
    """
    Draws a simple visual scale bar from 10 to 40 BMI,
    with a marker showing where the user's BMI falls.
    """
    scale_min, scale_max = 10, 40
    bar_length = 40

    clamped = max(scale_min, min(bmi, scale_max))
    position = int((clamped - scale_min) / (scale_max - scale_min) * bar_length)

    bar = ""
    zone_bounds = [18.5, 25, 30]
    zone_colors = [Colors.BLUE, Colors.GREEN, Colors.YELLOW, Colors.RED]

    for i in range(bar_length):
        value_at_i = scale_min + (i / bar_length) * (scale_max - scale_min)
        if value_at_i < zone_bounds[0]:
            color = zone_colors[0]
        elif value_at_i < zone_bounds[1]:
            color = zone_colors[1]
        elif value_at_i < zone_bounds[2]:
            color = zone_colors[2]
        else:
            color = zone_colors[3]

        if i == position:
            bar += Colors.BOLD + "▲" + Colors.RESET
        else:
            bar += color + "█" + Colors.RESET

    print(f"\n  {scale_min}" + " " * (bar_length - 6) + f"{scale_max}")
    print("  " + bar)
    print(f"  {Colors.GRAY}(marker ▲ shows your BMI position on the scale){Colors.RESET}")


def show_history():
    if not history:
        return
    print(f"\n{Colors.GRAY}--- Session History ---{Colors.RESET}")
    for i, (bmi, category) in enumerate(history, start=1):
        color = CATEGORY_INFO[category]["color"]
        print(f"  {i}. BMI {bmi:.2f} -> {color}{category}{Colors.RESET}")


def main():
    print_banner()

    weight = get_positive_float("Enter your weight in kg: ")
    height = get_positive_float("Enter your height in m (e.g. 1.75): ")

    bmi = calculate_bmi(weight, height)
    category = classify_bmi(bmi)
    info = CATEGORY_INFO[category]

    history.append((bmi, category))

    print(f"\n{Colors.BOLD}--- Result ---{Colors.RESET}")
    print(f"Your BMI is: {Colors.BOLD}{bmi:.2f}{Colors.RESET}")
    print(f"Category: {info['color']}{info['emoji']} {category}{Colors.RESET}")
    print(f"{Colors.GRAY}Tip: {info['tip']}{Colors.RESET}")

    draw_bmi_scale(bmi)
    show_history()


if __name__ == "__main__":
    while True:
        main()
        again = input(f"\n{Colors.CYAN}Calculate another BMI? (y/n): {Colors.RESET}").strip().lower()
        if again != "y":
            print(Colors.BOLD + "\nThanks for using the BMI Calculator. Stay healthy! 👋" + Colors.RESET)
            break
        print()
