"""
Random Password Generator (Beginner Tier - Command Line)
------------------------------------------------------------
Prompts the user for desired password length and character types,
then generates a random password matching all specified criteria.
"""

import random
import string


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    GRAY = "\033[90m"


def print_banner():
    print(Colors.CYAN + Colors.BOLD + "=" * 46)
    print("       🔐  RANDOM PASSWORD GENERATOR  🔐")
    print("=" * 46 + Colors.RESET)


def get_password_length():
    """Keeps asking until the user gives a valid length (min 8)."""
    while True:
        raw_value = input(Colors.CYAN + "Enter desired password length (min 8): " + Colors.RESET).strip()
        try:
            length = int(raw_value)
        except ValueError:
            print(Colors.RED + "  -> Invalid input. Please enter a whole number." + Colors.RESET)
            continue

        if length < 8:
            print(Colors.RED + "  -> Invalid length. Minimum allowed length is 8." + Colors.RESET)
            continue

        return length


def get_character_types():
    """
    Asks the user which character types to include.
    Requires at least 2 types to be selected.
    """
    while True:
        print("\nChoose character types to include (enter y/n for each):")
        use_upper = input("  Include uppercase letters (A-Z)? (y/n): ").strip().lower() == "y"
        use_lower = input("  Include lowercase letters (a-z)? (y/n): ").strip().lower() == "y"
        use_digits = input("  Include numbers (0-9)? (y/n): ").strip().lower() == "y"
        use_symbols = input("  Include symbols (!@#$...)? (y/n): ").strip().lower() == "y"

        selected_count = sum([use_upper, use_lower, use_digits, use_symbols])

        if selected_count < 2:
            print(Colors.RED + "  -> Invalid selection. Please select at least 2 character types." + Colors.RESET)
            continue

        return use_upper, use_lower, use_digits, use_symbols


def generate_password(length, use_upper, use_lower, use_digits, use_symbols):
    """
    Generates a random password of the given length that is
    guaranteed to include at least one character from each
    selected character type.
    """
    pools = []
    guaranteed_chars = []

    if use_upper:
        pools.append(string.ascii_uppercase)
        guaranteed_chars.append(random.choice(string.ascii_uppercase))
    if use_lower:
        pools.append(string.ascii_lowercase)
        guaranteed_chars.append(random.choice(string.ascii_lowercase))
    if use_digits:
        pools.append(string.digits)
        guaranteed_chars.append(random.choice(string.digits))
    if use_symbols:
        symbols = "!@#$%^&*()-_=+[]{};:,.<>?/"
        pools.append(symbols)
        guaranteed_chars.append(random.choice(symbols))

    # Combine all selected pools into one for filling the rest of the password
    combined_pool = "".join(pools)

    remaining_length = length - len(guaranteed_chars)
    remaining_chars = [random.choice(combined_pool) for _ in range(remaining_length)]

    password_chars = guaranteed_chars + remaining_chars
    random.shuffle(password_chars)

    return "".join(password_chars)


def main():
    print_banner()

    length = get_password_length()
    use_upper, use_lower, use_digits, use_symbols = get_character_types()

    password = generate_password(length, use_upper, use_lower, use_digits, use_symbols)

    print(f"\n{Colors.BOLD}--- Generated Password ---{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}{password}{Colors.RESET}")


if __name__ == "__main__":
    while True:
        main()
        again = input(f"\n{Colors.CYAN}Generate another password? (y/n): {Colors.RESET}").strip().lower()
        if again != "y":
            print(Colors.BOLD + "\nStay secure! 👋" + Colors.RESET)
            break
        print()
