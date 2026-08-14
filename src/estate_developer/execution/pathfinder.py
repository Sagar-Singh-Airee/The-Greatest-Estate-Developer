from __future__ import annotations

from estate_developer.state.parser import Position, ObservationState


class Pathfinder:
    """
    Computes optimal paths through the farm grid, avoiding collisions.
    """

    def find_path(self, state: ObservationState, start: Position, target: Position) -> list[Position]:
        """
        Returns a list of positions representing a path from start to target using A*.
        """
        import heapq
        
        if start == target:
            return [start]
            
        tiles = state.me.tiles
        max_y = len(tiles)
        max_x = len(tiles[0]) if max_y > 0 else 0
        
        def heuristic(a: tuple[int, int], b: tuple[int, int]) -> int:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
            
        open_set = []
        heapq.heappush(open_set, (0, (start.x, start.y)))
        came_from = {}
        g_score = {(start.x, start.y): 0}
        
        # Consider positions of other hands as obstacles
        # To avoid moving hands locking each other in this simple A*, we might only avoid static obstacles.
        # For this implementation, we allow passing through hands but not standing on them, 
        # or we could just consider them soft obstacles. For now, empty grid is walkable.
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == (target.x, target.y):
                # reconstruct path
                path = []
                while current in came_from:
                    path.append(Position(current[0], current[1]))
                    current = came_from[current]
                path.reverse()
                return path
                
            cx, cy = current
            # neighbors (4-way movement)
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                
                if 0 <= nx < max_x and 0 <= ny < max_y:
                    # In a full implementation, we'd check if (nx, ny) is a hard obstacle.
                    # Currently, farm tiles are generally walkable.
                    tentative_g_score = g_score[current] + 1
                    
                    neighbor = (nx, ny)
                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score = tentative_g_score + heuristic(neighbor, (target.x, target.y))
                        heapq.heappush(open_set, (f_score, neighbor))
                        
        return [] # no path found
