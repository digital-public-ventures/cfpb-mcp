#!/usr/bin/env python3
"""Demo script for Phase 4.5: CFPB UI integration.

Shows how to generate official CFPB dashboard URLs and capture screenshots.
"""

import httpx


def demo_url_generation():
    """Demonstrate URL generation for the official CFPB dashboard."""
    print('=' * 70)
    print('Phase 4.5 Demo: Official CFPB Dashboard Integration')
    print('=' * 70)
    print()

    base_url = 'http://localhost:8002'

    # Example 1: Simple search term
    print("Example 1: Search for 'foreclosure' complaints")
    print('-' * 70)
    r = httpx.get(f'{base_url}/cfpb-ui/url', params={'search_term': 'foreclosure'})
    data = r.json()
    print(f'Generated URL: {data["url"]}')
    print()

    # Example 2: Date range + product filter
    print('Example 2: Mortgage complaints in 2020-2023')
    print('-' * 70)
    r = httpx.get(
        f'{base_url}/cfpb-ui/url',
        params={
            'product': ['Mortgage'],
            'date_received_min': '2020-01-01',
            'date_received_max': '2023-12-31',
        },
    )
    data = r.json()
    print(f'Generated URL: {data["url"]}')
    print()

    # Example 3: Multi-company comparison
    print('Example 3: Compare Bank of America vs Wells Fargo')
    print('-' * 70)
    r = httpx.get(
        f'{base_url}/cfpb-ui/url',
        params={
            'company': [
                'BANK OF AMERICA, NATIONAL ASSOCIATION',
                'WELLS FARGO & COMPANY',
            ],
            'date_received_min': '2023-01-01',
        },
    )
    data = r.json()
    print(f'Generated URL: {data["url"]}')
    print()

    # Example 4: State-specific + has narrative
    print('Example 4: California complaints with consumer narratives')
    print('-' * 70)
    r = httpx.get(
        f'{base_url}/cfpb-ui/url',
        params={
            'state': ['CA'],
            'has_narrative': 'yes',
        },
    )
    data = r.json()
    print(f'Generated URL: {data["url"]}')
    print()

    print('=' * 70)
    print('Screenshot Service')
    print('=' * 70)
    print()
    print('To capture a screenshot of the official CFPB dashboard:')
    print(f'  GET {base_url}/cfpb-ui/screenshot?search_term=foreclosure')
    print()
    print('This returns a PNG image of the full CFPB dashboard with:')
    print('  • Official CFPB branding and styling')
    print('  • Interactive charts and visualizations')
    print('  • Pre-applied filters matching your query')
    print()
    print('Perfect for:')
    print('  • Creating authoritative reports')
    print('  • Sharing pre-configured dashboard views')
    print('  • Embedding official government visualizations')
    print()


if __name__ == '__main__':
    try:
        demo_url_generation()
    except httpx.ConnectError:
        print('Error: Server not running at http://localhost:8002')
        print('Start the server with: uv run python server.py')
