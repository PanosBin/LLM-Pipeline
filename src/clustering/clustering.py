from typing import List, Tuple
import logging
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from src.clustering.codebert_clustering import CodeBERTClustering
from src.parsers.objects import JavaMethod

logger = logging.getLogger(__name__)

def find_optimal_k(embeddings_np, min_k=2, max_k=15) -> int:
    best_k = min_k
    best_score = -1
    for k in range(min_k, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42)
        labels = kmeans.fit_predict(embeddings_np)
        score = silhouette_score(embeddings_np, labels)
        logger.info(f"k={k} | Silhouette Score={score:.3f}")
        if score > best_score:
            best_score = score
            best_k = k
    logger.info(f"Best number of clusters determined: {best_k}")
    return best_k

def cluster_methods_semantically(parsed_files: List) -> Tuple[List[List[JavaMethod]], CodeBERTClustering]:
    all_methods = [
        method for file in parsed_files
        for cls in file.classes
        for method in cls.methods
    ]

    if not all_methods:
        logger.warning("No methods found to cluster.")
        return [], None

    # Embed methods
    embedder = CodeBERTClustering()
    code_texts = [method.code for method in all_methods]
    embeddings = embedder.embedder.embed(code_texts).cpu().numpy()

    # Find best k with silhouette
    optimal_k = find_optimal_k(embeddings)
    logger.info(f"Clustering with optimal number of clusters: {optimal_k}")

    # Cluster with optimal k
    codebert_clusterer = CodeBERTClustering(n_clusters=optimal_k)
    codebert_clusterer.cluster(all_methods)
    clusters = codebert_clusterer.get_clusters()

    return clusters, codebert_clusterer

