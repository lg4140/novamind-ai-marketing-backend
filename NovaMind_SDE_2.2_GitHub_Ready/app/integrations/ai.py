"""AI provider port; reproducible fixture for demos without API access."""
from app.core.config import get_settings
from app.schemas import GeneratedContent, Newsletter, NewsletterSet

class ContentProviderError(RuntimeError):
    pass

def mock_content(topic: str) -> GeneratedContent:
    angles = {
        'ops_lead': ('Build repeatable processes', 'Automate repetitive approvals while retaining control'),
        'creative_director': ('Protect your creative time', 'Reduce interruptions without sacrificing originality'),
        'freelancer': ('Start small and win back hours', 'Choose a simple workflow you can improve this week'),
    }
    newsletters = {}
    for persona, (subject, angle) in angles.items():
        newsletters[persona] = Newsletter(
            subject=f'{subject}: {topic[:75]}',
            preview_text='Practical workflow ideas for small creative teams.',
            body=f'{angle}. Start by identifying one repeatable handoff in your team, measure cycle time, and review the impact after one week. This is a demo-only message, not an actual email.',
            cta_text='Read the guide',
        )
    # Purposefully deterministic; clearly marked as a fixture, not AI-generated output.
    paragraph = (f'When exploring {topic}, creative teams should first map the steps in their workflow. '
                 'Identify repetitive approvals, manual copying, and unclear handoffs. '
                 'Choose one small improvement, document the baseline, and test the change with a limited team. '
                 'Monitor quality and cycle time while preserving human review. '
                 'Keep a rollback option for failed changes. ')
    return GeneratedContent(
        topic=topic,
        blog_title=f'Practical Guide to {topic}',
        blog_outline=['Map the workflow', 'Prioritize pain points', 'Pilot safe automation', 'Measure outcomes'],
        blog_draft='\n\n'.join([paragraph] * 9),
        newsletters=NewsletterSet(**newsletters),
    )

def generate_content(topic: str) -> tuple[GeneratedContent, str]:
    settings = get_settings()
    if settings.ai_provider == 'mock':
        return mock_content(topic), 'mock'
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key, timeout=40.0, max_retries=1)
    prompt = (
        'You write practical B2B SaaS marketing content for NovaMind, a fictional AI workflow '
        'product for small creative agencies. Return one 400-600-word blog and newsletters for three personas: '
        'ops_lead (efficiency, margins), creative_director (creative time), freelancer (simple fast wins). '
        'Avoid invented case studies or unverifiable numerical claims. Return structured output for topic: ' + topic
    )
    try:
        response = client.responses.parse(
            model=settings.openai_model,
            input=[{'role':'user','content':prompt}],
            text_format=GeneratedContent,
            max_output_tokens=3500,
        )
        result = response.output_parsed
        if result is None:
            raise ContentProviderError('Model returned no parsed content.')
        if not 400 <= len(result.blog_draft.split()) <= 600:
            raise ContentProviderError('Blog length is outside 400-600 words.')
        return result, settings.openai_model
    except Exception as exc:
        raise ContentProviderError(f'Content provider failed: {type(exc).__name__}') from exc
