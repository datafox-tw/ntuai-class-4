import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from iceland_lab_web.services.knowledge import rebuild_knowledge_index, search_knowledge

print("Rebuilding index...")
stats = rebuild_knowledge_index()
print(f"Stats: {stats}")

print("\nSearching for 'Blue Lagoon'...")
results = search_knowledge("Blue Lagoon")
for r in results:
    print(f"- [{r['score']:.2f}] {r['title']}: {r['snippet'][:100]}...")
