"""Search and explore career paths through the job graph."""


from collections import defaultdict



def load_job_graph(records):
    """Organize transition records by source job ID."""

    adjacency = defaultdict(list)

    for edge in records:
        source_id = str(edge["source_job_id"])
        target_id = str(edge["target_job_id"])

        adjacency[source_id].append({
            "target_job_id": target_id,
            "score": float(edge["transition_score"]),
            "move_type": edge["move_type"],
            "transition_reason": edge.get("transition_reason", ""),
            "qualification_gaps": edge.get("qualification_gap_terms", []),
        })

    return dict(adjacency)


def find_path(graph, start_job_id, destination_job_id):
    """Find the shortest path between two jobs using BFS."""
    from collections import deque

    queue = deque([[str(start_job_id)]])
    visited = {str(start_job_id)}

    while queue:
        path = queue.popleft()
        current_job = path[-1]

        if current_job == str(destination_job_id):
            return path

        for connection in graph.get(current_job, []):
            next_job = connection["target_job_id"]

            if next_job not in visited:
                visited.add(next_job)
                queue.append(path + [next_job])

    return None


def find_multiple_paths(graph, start_job_id, destination_job_id, max_paths=5):
    """Find multiple simple paths between two jobs."""
    from collections import deque

    start = str(start_job_id)
    destination = str(destination_job_id)

    queue = deque([[start]])
    paths = []

    while queue and len(paths) < max_paths:
        path = queue.popleft()
        current_job = path[-1]

        if current_job == destination:
            paths.append(path)
            continue

        for connection in graph.get(current_job, []):
            next_job = connection["target_job_id"]

            if next_job not in path:
                queue.append(path + [next_job])

    return paths


def rank_paths(graph, paths):
    """Rank paths by their average transition explanations."""
    ranked_paths = []

    for path in paths:
        scores = []
        step_reasons = []
        qualification_gaps = []

        for i in range(len(path) - 1):
            current_job = path[i]
            next_job = path[i + 1]

            for connection in graph.get(current_job, []):
                if connection["target_job_id"] == next_job:
                    scores.append(connection["score"])
                    step_reasons.append(connection.get("transition_reason", ""))
                    qualification_gaps.append(connection.get("qualification_gaps", []))
                    break

        average_score = sum(scores) / len(scores) if scores else 0

        ranked_paths.append({
            "path": path,
            "average_score": average_score,
            "path_length": len(path) - 1,
            "step_reasons": step_reasons,
            "qualification_gaps": qualification_gaps,
        })

    return sorted(
        ranked_paths,
        key=lambda item: (item["average_score"], -item["path_length"]),
        reverse=True,
    )


def format_paths(ranked_paths):
    """Format ranked paths for the web app."""
    formatted = []

    for item in ranked_paths:
        formatted.append({
            "ordered_job_ids": item["path"],
            "path_length": item["path_length"],
            "path_score": item["average_score"],
            "step_reasons": item.get("step_reasons", []),
            "qualification_gaps": item.get("qualification_gaps", []),
        })

    return formatted


def explore_paths(graph, start_job_id, max_depth=3, max_paths=20):
    """Explore possible career paths from a starting job."""
    from collections import deque 
    start = str(start_job_id)
    queue = deque([[start]])
    paths = []

    while queue and len(paths) < max_paths:
        path = queue.popleft()
        current_job = path[-1]

        if len(path) - 1 >= max_depth:
            continue

        for connection in graph.get(current_job, []):
            next_job = connection["target_job_id"]

            if next_job not in path:
                new_path = path + [next_job]
                paths.append(new_path)
                queue.append(new_path)

                if len(paths) >= max_paths:
                    break

    return paths


def diversify_paths(ranked_paths, max_paths=5, threshold=0.7):
    """Select high-scoring paths with different intermediate jobs."""
    selected = []

    for candidate in ranked_paths:
        candidate_jobs = set(candidate["path"][1:-1])

        too_similar = False

        for existing in selected:
            existing_jobs = set(existing["path"][1:-1])
            union = candidate_jobs | existing_jobs
            intersection = candidate_jobs & existing_jobs

            similarity = (len(intersection) / len(union) if union else 1.0)

            if similarity >= threshold:
                too_similar = True
                break

        if not too_similar:
            selected.append(candidate)

        if len(selected) >= max_paths:
            break

    return selected





