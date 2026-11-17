"""KFall task descriptions and demo videos from the official reference table.

https://docs.google.com/spreadsheets/d/1bkMwB1e_gjYQm-7r2Ago73zv9xzDxeR3lg7WO0toO0E/
"""

KFALL_REFERENCE_URL = "https://sites.google.com/view/kfalldataset"

# Task IDs, not Dxx activity numbers: D20/D21 correspond to T35/T36.
TASKS = {
    1: ("Permanecer de pie durante 30 segundos", "1VC9YeNUX5iWngpu-S94x4Fuk9oLpkiVO"),
    2: ("De pie, inclinar lentamente la espalda, con o sin flexionar las rodillas, atarse los cordones y levantarse", "1V3S83c_-9jJPd1_f3Uz5k4TUf7CZ9MDi"),
    3: ("Recoger un objeto del suelo", None),
    4: ("Saltar suavemente para intentar alcanzar un objeto", "1Cxsfg2H2-aeIqhE80eHXuaIq5pspSKFG"),
    5: ("De pie, sentarse en el suelo, esperar un momento y levantarse a velocidad normal", "16oLSgn_oJhDkZMaFIRXW3iX9Ds2uO58u"),
    6: ("Caminar normalmente con un giro (4 m)", "1WB0yQWizV00LpXCy7AFN0m-hzMxvgFft"),
    7: ("Caminar rápidamente con un giro (4 m)", "1F5bKRfYjLYmO9VTFCn7QWcLmtkTdwOqY"),
    8: ("Trotar normalmente con un giro (4 m)", "1Mb_p5Vkqg-D4HwledEUTZDfbNQJholsA"),
    9: ("Trotar rápidamente con un giro (4 m)", "1xHyqT9C797k9E-iWAjmgMNDbjbL10-dQ"),
    10: ("Tropezar mientras se camina", "1gqXHZi-uvDvBVXp8c5fdC76iboTTGwoS"),
    11: ("Permanecer sentado en una silla durante 30 segundos", "170KBG91GYHtwlkTqiM75ck2z8YxiQDOp"),
    12: ("Permanecer sentado en el sofá, con la espalda apoyada, durante 30 segundos", "1LyzGPmVhdCPHszmg6P7pNwQYUjmejOfs"),
    13: ("Sentarse en una silla y levantarse a velocidad normal", "1LzBfDBCkUQloUX8DOCsemk68FmQt6qnx"),
    14: ("Sentarse en una silla y levantarse rápidamente", "1koJr0hiyNtGXV5wh4NoGUuh0CcBGvJI5"),
    15: ("Sentarse un momento, intentar levantarse y desplomarse sobre la silla", "1FyhQMUhbsWE3ZDoUXVCGLttpztDqtc_9"),
    16: ("De pie, sentarse en el sofá con la espalda apoyada y levantarse normalmente", "1aLaXW72Pf850Ns-hwHVanugOCfg7Tska"),
    17: ("Permanecer acostado en la cama durante 30 segundos", "1NSPXSDNoCZqX8Sx55-v9tTkZ4oH_SNaw"),
    18: ("Sentarse un momento, acostarse en la cama y levantarse a velocidad normal", "1l1BKfyiELnmZ2zAmYfM3__6dIe5nHHYA"),
    19: ("Sentarse un momento, acostarse en la cama y levantarse rápidamente", "1WJZAFdH8PORp8xjGupI1eq5w9u11jBOe"),
    20: ("Caída hacia delante al intentar sentarse", "1ZabrBRTs-w3Wp68jlxKMHJYkZLo_0Yts"),
    21: ("Caída hacia atrás al intentar sentarse", "1ADL0crYiFAwjwwcoaPugy0X99gwF9g4r"),
    22: ("Caída lateral al intentar sentarse", "1Yco-nIFmAIdgEBwMFLtJm-FmdZ8Cakli"),
    23: ("Caída hacia delante al intentar levantarse", "1vm6ziFsZCdeLlep-7UF5H5D0WRaMYq5b"),
    24: ("Caída lateral al intentar levantarse", "1fb6Ap3JV2UK28eRxLyD9hQx2nApnPbot"),
    25: ("Caída hacia delante estando sentado, por desmayo", "1mnwGb0XX48kYpttvWTaMKkdvc46sy5PK"),
    26: ("Caída lateral estando sentado, por desmayo", "1qBExvg2NlE920cRNYonp4yUPjjMDkOAM"),
    27: ("Caída hacia atrás estando sentado, por desmayo", "1YKDFy4Pn46T1BjhtSjmmXo-J7QcG0oj2"),
    28: ("Caída vertical hacia delante al caminar, por desmayo", "1ROlwLhy72W_fC2vZT1W5hDtt0CHNT3zD"),
    29: ("Caída al caminar por desmayo, usando las manos para amortiguar la caída", "1n-w64lZFAzRgL655rpyMImoXafXfXVZq"),
    30: ("Caída hacia delante al caminar, por un tropiezo", "1nMuCVOXGUYLDJM8pFbj8IhEmQEUePhah"),
    31: ("Caída hacia delante al trotar, por un tropiezo", "1kadV34MgOrqaD31QXv8tQxbz_mAz5xGQ"),
    32: ("Caída hacia delante al caminar, por un resbalón", "1mi7AOI8SCsS3RDzKLPdZolQ6OGkcwU9y"),
    33: ("Caída lateral al caminar, por un resbalón", "1_nk53ib3jqrhzYRo2t-a-IMkNM2Un57B"),
    34: ("Caída hacia atrás al caminar, por un resbalón", "1oiGrWt3tcqjnZqX7yoLUynP-YCv7-XCh"),
    35: ("Subir y bajar escaleras normalmente (5 escalones)", "150RVWzwaRQ9xpooAO9_9lKZaCTXH9jWC"),
    36: ("Subir y bajar escaleras rápidamente (5 escalones)", "1haCkczFNkdxkugTL1zwx0SCpb4FAhIyR"),
}
TASK_DESCRIPTIONS = {f"T{task:02d}": description for task, (description, _) in TASKS.items()}
KFALL_TASK_REFERENCE_VIDEOS = {
    task: f"https://drive.google.com/file/d/{video}/view?usp=sharing"
    for task, (_, video) in TASKS.items() if video is not None
}
