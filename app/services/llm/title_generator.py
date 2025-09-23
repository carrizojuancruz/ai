from __future__ import annotations

import json
import logging
import re

import boto3
from botocore.exceptions import ClientError

from app.core.config import config

logger = logging.getLogger(__name__)


class TitleGeneratorLLM:
    """LLM client for generating titles and summaries using AWS Bedrock."""

    def __init__(self) -> None:
        self.region = config.get_aws_region()
        if not self.region:
            raise RuntimeError("AWS_REGION is required for Bedrock provider")

        # Use GPT-OSS model for title generation
        self.model_id = config.TITLE_GENERATOR_MODEL_ID
        self.bedrock_client = boto3.client("bedrock-runtime", region_name=self.region)

    async def generate_title_and_summary(self, body: str) -> dict[str, str]:
        """Generate title and summary from content body."""
        system_prompt = """You are an expert assistant in creating concise titles and summaries for financial content.
        Your task is to generate an attractive title and a summary of maximum 125 characters for the provided content.

        Rules:
        1. The title should be clear, descriptive, and attractive
        2. The summary should capture the essence of the content in maximum 125 characters
        3. Respond ONLY with a valid JSON with the keys "title" and "summary"
        4. Do not include additional explanations"""

        user_prompt = f"""Analyze the following content and generate a title and summary:

        Content:
        {body}

        Respond with the JSON format:s
        {{"title": "title here", "summary": "summary here"}}"""

        try:
            # Prepare the request for GPT-OSS
            request_body = {
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "max_tokens": 300,
                "temperature": config.TITLE_GENERATOR_TEMPERATURE
            }

            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            content = response_body['choices'][0]['message']['content']


            # Parse the JSON response from the model
            try:
                content = content.strip()
                content = re.sub(r'<reasoning>.*?</reasoning>', '', content, flags=re.DOTALL)
                content = content.strip()

                json_start = content.find('{')
                if json_start != -1:
                    json_content = content[json_start:]
                    json_end = json_content.rfind('}')
                    if json_end != -1:
                        json_content = json_content[:json_end + 1]
                        result = json.loads(json_content)
                    else:
                        raise json.JSONDecodeError("No closing brace found", content, 0)
                else:
                    raise json.JSONDecodeError("No JSON found in response", content, 0)

                # Ensure summary doesn't exceed 125 characters
                if len(result.get("summary", "")) > 125:
                    result["summary"] = result["summary"][:122] + "..."

                return {
                    "title": result.get("title", ""),
                    "summary": result.get("summary", "")
                }
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {content}")
                # Fallback: extract title and summary manually
                return self._fallback_extraction(body)

        except ClientError as e:
            logger.error(f"Error calling Bedrock API: {e}")
            raise RuntimeError(f"Failed to generate title and summary: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error in title generation: {e}")
            raise RuntimeError(f"Unexpected error: {e}") from e

    def _fallback_extraction(self, body: str) -> dict[str, str]:
        """Fallback method to generate title and summary if LLM fails."""
        # Simple fallback: use first sentence as title, truncated body as summary
        sentences = body.split('.')
        title = sentences[0][:50] if sentences else "Financial Content"

        summary = body[:122].strip()
        if len(body) > 122:
            summary += "..."

        return {
            "title": title,
            "summary": summary
        }
