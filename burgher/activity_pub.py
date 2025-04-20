import os, json


def write_activity_pub(output_folder, full_url, albums, username, domain):
    os.makedirs(output_folder / '.well-known/', exist_ok=True)
    os.makedirs(output_folder / 'users/', exist_ok=True)

    user_data = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "id": f"https://{domain}/users/{username}",
        "type": "Person",
        "name": username,
        "preferredUsername": username,
        "inbox": f"{full_url}/inbox",
        "outbox": f"{full_url}/outbox",
        "followers": f"{full_url}/followers",
        "url": f"{full_url}/",
        # "icon": {
        #     "type": "Image",
        #     "url": "https://tintinburghcom/avatar.png"
        # }
    }

    with open(output_folder / f"{username}.json", 'w') as f:
        f.write(json.dumps(
            user_data
        ))
    with open(output_folder / f"users/{username}.json", 'w') as f:
        f.write(json.dumps(
            user_data
        ))

    links = [
        {
            "id": a.get_activity_pub_url(),
            "type": "Note",
            "sensitive": False,

            "content": a.get_name(),
            "url": a.get_activity_pub_url(),
            "to": [
                "https://www.w3.org/ns/activitystreams#Public"
            ],
            "published": a.get_latest_date().isoformat(),
            "updated": a.get_latest_date().isoformat(),
        } for a in albums
    ]

    with open(output_folder / "outbox.json", 'w') as f:
        f.write(json.dumps(
            {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": f"{full_url}/outbox.json",
                "type": "OrderedCollection",
                "totalItems": len(links),
                "orderedItems": links
            }
        ))
    with open(output_folder / "inbox.json", 'w') as f:
        f.write(json.dumps(
            {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": f"{full_url}/inbox.json",
                "type": "OrderedCollection",
                "totalItems": 0,
                "orderedItems": []
            }
        ))
    with open(output_folder / "followers.json", 'w') as f:
        f.write(json.dumps(
            {
                "@context": "https://www.w3.org/ns/activitystreams",
                "id": f"{full_url}/followers.json",
                "type": "OrderedCollection",
                "totalItems": 0,
                "orderedItems": []
            }
        ))

    with open(output_folder / '.well-known/' / "webfinger.json", 'w') as f:
        f.write(json.dumps(
            {
                "subject": f"acct:{username}@{domain}",
                "links": [
                    {
                        "rel": "self",
                        "type": "application/activity+json",
                        "href": f"{full_url}/{username}"
                    }
                ]
            }
        ))
