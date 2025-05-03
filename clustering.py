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

    def fit(self, data_list):
        """
        data_list: List of dicts:
            - title: main heading (OR 'heading' as fallback)
            - introduction: string
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
                'distance': dist
            })
        return results


def init_clusters(n_clusters=3, num_closest_clusters=1):
    json_file = 'corpus.json'
    with open(json_file, 'r', encoding='utf-8') as f:
        data_list = json.load(f)

    clusterer = RAGClusterer(n_clusters, num_closest_clusters=num_closest_clusters)
    clusterer.fit(data_list)  # Your data_list can have 'title' or 'heading' keys.
    return clusterer


def query_clusters(clusterer, query, top_x=None, top_y=3):
    closest_clusters = clusterer.find_closest_clusters(query, top_x)
    cluster_ids = [cid for cid, _ in closest_clusters]

    top_chunks = clusterer.find_closest_chunks_in_clusters(query, cluster_ids, top_y)    
    return top_chunks




if __name__ == "__main__":
    clusterer = init_clusters()
    print(query_clusters(clusterer, "Real-Time tab missing in Simulink"))

    # json_file = 'corpus.json'
    # with open(json_file, 'r', encoding='utf-8') as f:
    #     data_list = json.load(f)

    # n_clusters = 3
    # num_closest_clusters = 1  # New parameter

    # clusterer = RAGClusterer(n_clusters, num_closest_clusters=num_closest_clusters)
    # clusterer.fit(data_list)  # Your data_list can have 'title' or 'heading' keys.
    # clusterer.print_clusters()
    # print("\nCluster centroid shape:", clusterer.get_cluster_centroids().shape)

    # query = "Real-Time tab missing in Simulink"
    # closest_clusters = clusterer.find_closest_clusters(query)
    # print("\nClosest clusters (default num_closest_clusters):", closest_clusters)

    # # You can still override if needed:
    # closest_clusters_override = clusterer.find_closest_clusters(query, top_x=3)
    # print("\nClosest clusters (override top_x=3):", closest_clusters_override)

    # # Search chunks in clusters
    # cluster_ids = [cid for cid, _ in closest_clusters]
    # top_chunks = clusterer.find_closest_chunks_in_clusters(query, cluster_ids, top_y=3)
    # print("\nTop chunks:")
    # for chunk in top_chunks:
    #     print(f"- Cluster {chunk['cluster_id']} > {chunk['title']} > {chunk['heading']} (distance: {chunk['distance']:.4f})")
