def get_version() -> str:
    """
    Returns the version details. Do not Interfere with this !

    :return: The version details in the format 'vMAJOR.MINOR'
    :rtype: str
    """
    MAJOR = "2"
    MINOR = "0"
    return f"v{MAJOR}.{MINOR}"


if __name__ == "__main__":
    print(get_version())
