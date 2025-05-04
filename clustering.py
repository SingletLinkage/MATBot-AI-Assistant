from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import json

class RAGClusterer:
    def __init__(self, n_clusters, embedding_model='all-MiniLM-L6-v2', num_closest_clusters=1):
        """
        n_clusters: Number of clusters to create.
        embedding_model: SentenceTransformer model.
        num_closest_clusters: Default number of closest clusters to fetch (can override later).
        """
        self.n_clusters = n_clusters
        self.num_closest_clusters = num_closest_clusters
        self.model = SentenceTransformer(embedding_model)
        self.kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        self.cluster_titles = {}  # {cluster_id: [title, title, ...]}
        self.cluster_centroids = None
        self.cluster_index = None
        self.chunk_store = []  # List of chunks with metadata and embeddings
        self.self_memory_store = []  # List of self-memory dicts for previous interactions

    def fit(self, data_list):
        """
        data_list: List of dicts:
            - title: main heading (OR 'heading' as fallback)
            - introduction: string
            - link: string
            - chunks: optional list of dicts {'heading': ..., 'content': ...}
            - content: optional full content (used if chunks missing)
        """
        titles = [item.get('title') or item.get('heading') for item in data_list]

        # Encode titles
        title_embeddings = self.model.encode(titles, show_progress_bar=False).astype(np.float32)

        # Cluster titles
        self.kmeans.fit(title_embeddings)
        labels = self.kmeans.labels_
        self.cluster_centroids = self.kmeans.cluster_centers_.astype(np.float32)

        # Organize titles by cluster
        for idx, label in enumerate(labels):
            if label not in self.cluster_titles:
                self.cluster_titles[label] = []
            self.cluster_titles[label].append(titles[idx])

        # Build chunks (with cluster_id metadata)
        for idx, item in enumerate(data_list):
            cluster_id = labels[idx]
            title = item.get('title') or item.get('heading')
            introduction = item.get('introduction', '')
            chunks = item.get('chunks', [])
            link = item.get('link', '')
            fallback_content = item.get('content', '')

            if chunks:
                for chunk in chunks:
                    full_content = f"{introduction} {chunk['content']}".strip()
                    combined_text = f"{chunk['heading']}. {full_content}"
                    embedding = self.model.encode([combined_text], show_progress_bar=False).astype(np.float32)[0]
                    self.chunk_store.append({
                        'cluster_id': cluster_id,
                        'title': title,
                        'heading': chunk['heading'],
                        'content': full_content,
                        'link': link,
                        'embedding': embedding
                    })
            else:
                # Fallback: create 1 chunk with title as heading
                full_content = f"{introduction} {fallback_content}".strip()
                combined_text = f"{title}. {full_content}"
                embedding = self.model.encode([combined_text], show_progress_bar=False).astype(np.float32)[0]
                self.chunk_store.append({
                    'cluster_id': cluster_id,
                    'title': title,
                    'heading': title,
                    'content': full_content,
                    'link': link,
                    'embedding': embedding
                })

        # Build FAISS index for cluster centroids
        dim = self.cluster_centroids.shape[1]
        self.cluster_index = faiss.IndexFlatL2(dim)
        self.cluster_index.add(self.cluster_centroids)

    def print_clusters(self):
        """
        Print the titles under each cluster.
        """
        for cluster_id, titles in self.cluster_titles.items():
            print(f"\nCluster {cluster_id}:")
            for t in titles:
                print(f"  - {t}")

    def get_num_clusters(self):
        return self.n_clusters

    def get_cluster_centroids(self):
        if self.cluster_centroids is None:
            raise ValueError("Run fit() first.")
        return self.cluster_centroids

    def find_closest_clusters(self, query, top_x=None):
        """
        Search closest clusters by their centroid embeddings.

        If top_x is not specified, defaults to self.num_closest_clusters.
        """
        if self.cluster_index is None:
            raise ValueError("Run fit() first.")

        if top_x is None:
            top_x = self.num_closest_clusters

        query_emb = self.model.encode([query], show_progress_bar=False).astype(np.float32)
        distances, indices = self.cluster_index.search(query_emb, top_x)
        return [(int(indices[0][i]), distances[0][i]) for i in range(top_x)]

    def find_closest_chunks_in_clusters(self, query, cluster_ids, top_y=3):
        """
        Search chunks within the selected clusters.
        """
        relevant_chunks = [c for c in self.chunk_store if c['cluster_id'] in cluster_ids]

        if not relevant_chunks:
            return []

        chunk_embs = np.array([c['embedding'] for c in relevant_chunks]).astype(np.float32)
        dim = chunk_embs.shape[1]
        temp_index = faiss.IndexFlatL2(dim)
        temp_index.add(chunk_embs)

        query_emb = self.model.encode([query], show_progress_bar=False).astype(np.float32)
        distances, indices = temp_index.search(query_emb, top_y)

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            c = relevant_chunks[idx]
            results.append({
                'cluster_id': c['cluster_id'],
                'title': c['title'],
                'heading': c['heading'],
                'content': c['content'],
                'link': c['link'],
                'distance': dist
            })
        return results

    def add_to_self_memory(self, query, context, output, score):
        """
        Stores a generated output as self-memory with its embedding.
        Only adds to memory if score is high enough (quality threshold).
        
        Args:
            query: The user's original query
            context: The retrieved context used for generating the response
            output: The generated response
            score: The quality score of the response (0-1)
        """
        combined_text = f"{query} {context} {output}"
        embedding = self.model.encode([combined_text], show_progress_bar=False).astype(np.float32)[0]
        
        # Only store high-quality responses (score > 0.9)
        if score > 0.9:
            self.self_memory_store.append({
                'query': query,
                'context': context, 
                'output': output,
                'embedding': embedding,
                'score': score
            })
            return True
        return False

    def find_closest_self_memory(self, query, top_k=3):
        """
        Safe: Returns empty list if self-memory store is empty.
        
        Args:
            query: The user query to find similar memories for
            top_k: Number of memories to retrieve
            
        Returns:
            List of dictionaries containing closest memories and their distances
        """
        if not self.self_memory_store:
            return []

        # Encode query
        query_emb = self.model.encode([query], show_progress_bar=False).astype(np.float32)
        
        # Extract embeddings from memory store
        mem_embs = np.array([m['embedding'] for m in self.self_memory_store]).astype(np.float32)
        dim = mem_embs.shape[1]
        
        # Create temporary FAISS index for search
        temp_index = faiss.IndexFlatL2(dim)
        temp_index.add(mem_embs)
        
        # Search for closest memories
        distances, indices = temp_index.search(query_emb, min(top_k, len(self.self_memory_store)))

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            m = self.self_memory_store[idx]
            results.append({
                'query': m['query'],
                'context': m['context'],
                'output': m['output'],
                'distance': float(dist),  # Convert to native Python float
                'score': m.get('score', 1.0)  # Include original score if available
            })
        return results

    def query_clusters(self, query, top_x=None, top_y=3, top_k_self=3):
        """
        Retrieves from both clustered external DB and self-memory.
        Compares best result from each and returns the best context.
        
        Args:
            query: The user query
            top_x: Number of closest clusters to search
            top_y: Number of documents to retrieve from each cluster
            top_k_self: Number of self-memories to retrieve
            
        Returns:
            Dictionary with source type and best matching data
        """
        # Step 1: External clustered retrieval
        closest_clusters = self.find_closest_clusters(query, top_x)
        cluster_ids = [cid for cid, _ in closest_clusters]
        top_chunks = self.find_closest_chunks_in_clusters(query, cluster_ids, top_y)

        # Take best chunk (smallest distance)
        best_chunk = None
        if top_chunks:
            best_chunk = min(top_chunks, key=lambda c: c['distance'])

        # Step 2: Self-memory retrieval
        top_self_memories = self.find_closest_self_memory(query, top_k_self)

        # Take best self-memory (smallest distance)
        best_self = None
        if top_self_memories:
            best_self = min(top_self_memories, key=lambda c: c['distance'])

        # Step 3: Compare best_chunk vs best_self
        if best_chunk and best_self:
            # Compare distances to determine which source to use
            # We might prioritize self-memory if distances are close
            if best_self['distance'] < best_chunk['distance']:
                return {
                    'source': 'self_memory',
                    'data': best_self
                }
            else:
                return {
                    'source': 'clustered_db',
                    'data': best_chunk
                }
        elif best_chunk:
            return {
                'source': 'clustered_db',
                'data': best_chunk
            }
        elif best_self:
            return {
                'source': 'self_memory',
                'data': best_self
            }
        else:
            return {
                'source': None,
                'data': None
            }

    def save_self_memory(self, file_path):
        """
        Save self memory to a JSON file.
        Embeddings are converted to lists for JSON serialization.
        """
        # Create a copy of the memory store with serializable embeddings
        serializable_memory = []
        for mem in self.self_memory_store:
            serializable_mem = mem.copy()
            serializable_mem['embedding'] = mem['embedding'].tolist()
            serializable_memory.append(serializable_mem)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_memory, f)
            
    def load_self_memory(self, file_path):
        """
        Load self memory from a JSON file.
        Converts lists back to numpy arrays for embeddings.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                serialized_memory = json.load(f)
                
            self.self_memory_store = []
            for mem in serialized_memory:
                mem['embedding'] = np.array(mem['embedding'], dtype=np.float32)
                self.self_memory_store.append(mem)
            
            return len(self.self_memory_store)
        except (FileNotFoundError, json.JSONDecodeError):
            self.self_memory_store = []
            return 0


def init_clusters(json_file="corpus.json", n_clusters=10, num_closest_clusters=1, memory_file=None):
    """
    Initialize the RAGClusterer with data and optionally load self-memory.
    
    Args:
        json_file: Path to the corpus JSON file
        n_clusters: Number of clusters to create
        num_closest_clusters: Default number of closest clusters to fetch
        memory_file: Optional path to load/initialize self-memory
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data_list = json.load(f)

    clusterer = RAGClusterer(n_clusters, num_closest_clusters=num_closest_clusters)
    clusterer.fit(data_list)
    
    # Load self-memory if file path is provided
    if memory_file:
        try:
            mem_count = clusterer.load_self_memory(memory_file)
            print(f"Loaded {mem_count} self-memory entries from {memory_file}")
        except Exception as e:
            print(f"Could not load self-memory: {e}")
    
    return clusterer


def query_clusters(clusterer, query, top_x=None, top_y=3, top_k_self=3, use_self_memory=True):
    """
    Query the clusterer, optionally using self-memory.
    
    Args:
        clusterer: Initialized RAGClusterer
        query: User query string
        top_x: Number of clusters to retrieve
        top_y: Number of chunks per cluster to retrieve
        top_k_self: Number of self-memory entries to check
        use_self_memory: Whether to include self-memory in search
    """
    if use_self_memory:
        # Use the combined query mechanism that checks both clusters and self-memory
        result = clusterer.query_clusters(query, top_x=top_x, top_y=top_y, top_k_self=top_k_self)
        if result['source'] == 'self_memory':
            # For self-memory results, return a formatted list matching external retrieval format
            self_memory_data = result['data']
            return [{
                'cluster_id': -1,  # -1 indicates self-memory
                'title': f"Previous Interaction: {self_memory_data['query'][:50]}...",
                'heading': "Self-Memory",
                'content': self_memory_data['output'],
                'link': '',
                'distance': self_memory_data['distance'],
                'source': 'self_memory',
                'original_query': self_memory_data['query']
            }]
        elif result['source'] == 'clustered_db':
            # For regular results, return as list with each chunk having 'source' field
            closest_clusters = clusterer.find_closest_clusters(query, top_x)
            cluster_ids = [cid for cid, _ in closest_clusters]
            top_chunks = clusterer.find_closest_chunks_in_clusters(query, cluster_ids, top_y)
            # Add source information to each chunk
            for chunk in top_chunks:
                chunk['source'] = 'clustered_db'
            return top_chunks
    else:
        # Original behavior - just use external retrieval
        closest_clusters = clusterer.find_closest_clusters(query, top_x)
        cluster_ids = [cid for cid, _ in closest_clusters]
        top_chunks = clusterer.find_closest_chunks_in_clusters(query, cluster_ids, top_y)
        for chunk in top_chunks:
            chunk['source'] = 'clustered_db'
        return top_chunks


if __name__ == "__main__":
    # Simple test to demonstrate self-memory
    memory_file = "self_memory.json"
    clusterer = init_clusters(n_clusters=30, num_closest_clusters=5, memory_file=memory_file)
    
    # Test query
    from pprint import pprint
    query = "How to fix sample time issues in Simulink?"
    print(f"\nQuerying: '{query}'")
    results = query_clusters(clusterer, query, top_y=3, use_self_memory=True)
    
    # Print result source and first result details
    if results:
        source_type = results[0].get('source', 'unknown')
        print(f"Result source: {source_type}")
        if source_type == 'self_memory':
            print("Using previous interaction result!")
        pprint(results[0])
    else:
        print("No results found.")
