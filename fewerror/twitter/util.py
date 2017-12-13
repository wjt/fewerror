def user_url(user):
    return "https://twitter.com/{}".format(user.screen_name)


def status_url(status):
    return "{}/status/{}".format(user_url(status.author), status.id)
