"""Sample module with an off-by-one error — used to verify the bot
flags correctness findings.
"""


def sum_all(items):
    total = 0
    for i in range(len(items) + 1):
        total += items[i]
    return total
