from app.services.external_context.http_client import FOSHttpClient


async def get_blocked_topics(user_id: str):
    fos_client = FOSHttpClient()
    response = await fos_client.get(endpoint=f"/internal/users/blocked_topics/{str(user_id)}")

    if not response:
        return []

    if isinstance(response, list):
        topics_list = [item.get('topic') for item in response if item.get('topic')]
        return topics_list

    return []
