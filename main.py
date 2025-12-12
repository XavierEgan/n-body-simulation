import pygame
import random
from dataclasses import dataclass
from typing import Literal
import time

G = 6.67430e-11
SCREEN_SIZE = (800, 600)
AU_M = 1.5e11
ZOOM_FACTOR = .5 # 1 = earth is 100 px from centre of sun
PLANET_SCALE = 2 # multiplier for planet radii, can be uesd to counteract zoom scaling the planets too small

LOGGING_ENABLED = True
VISUALIZE_ENABLED = False

timestep = 3600 * 50 # seconds per frame (one hour)

def meters_to_pix(meters:pygame.math.Vector2) -> tuple[int, int]:
    return (int(meters.x / (1.5e9 / ZOOM_FACTOR)) + SCREEN_SIZE[0] // 2, int(meters.y / (1.5e9 / ZOOM_FACTOR)) + SCREEN_SIZE[1] // 2)

class Body:
    def __init__(self, name:str, pos:pygame.math.Vector2, vel:pygame.math.Vector2, mass:float, radius:int, color:pygame.Color):
        self.name: str = name
        self.pos: pygame.math.Vector2 = pos 
        self.vel: pygame.math.Vector2 = vel
        self.mass: float = mass
        self.radius: int = radius
        self.color: pygame.Color = color

    def draw(self, screen:pygame.Surface):
        pygame.draw.circle(screen, self.color, meters_to_pix(self.pos), int(self.radius * ZOOM_FACTOR * PLANET_SCALE))

    def update_naeve(self, bodies:list['Body'], dt:float):
        total_acceleration = pygame.math.Vector2(0, 0)
        for other in bodies:
            if other is self:
                continue
            direction = other.pos - self.pos
            distance_2 = direction.length_squared()
            if distance_2 == 0:
                continue
            acceleration = G * other.mass / distance_2

            total_acceleration += direction.normalize() * acceleration
        self.vel += total_acceleration * dt
        self.pos += self.vel * dt

    def update(self, barnes_hut_root:'BarnesHutNode', dt:float):
        net_force = pygame.math.Vector2(0, 0)
        theta = 0.5

        def calc_net_force(node: 'BarnesHutNode'):
            nonlocal net_force

            if BarnesHutNode.is_external(node) and node.body is not self:
                if (not node.body):
                    return

                # calc the force by node on this
                direction = node.body.pos - self.pos
                distance_2 = direction.length_squared()
                if distance_2 == 0:
                    return
                force_magnitude = G * self.mass * node.body.mass / distance_2
                net_force += direction.normalize() * force_magnitude
            elif BarnesHutNode.is_internal(node):
                s = node.boundary.width  # assuming square boundary
                d = (node.center_of_mass - self.pos).length()
                if d == 0:
                    return
                if (s / d) < theta:
                    # treat this node as a single body
                    direction = node.center_of_mass - self.pos
                    distance_2 = direction.length_squared()
                    if distance_2 == 0:
                        return
                    force_magnitude = G * self.mass * node.total_mass / distance_2
                    net_force += direction.normalize() * force_magnitude
                else:
                    # recurse into children
                    if node.nw:
                        calc_net_force(node.nw)
                    if node.ne:
                        calc_net_force(node.ne)
                    if node.sw:
                        calc_net_force(node.sw)
                    if node.se:
                        calc_net_force(node.se)
        
        calc_net_force(barnes_hut_root)

        acceleration = net_force / self.mass
        self.vel += acceleration * dt
        self.pos += self.vel * dt
    
    @staticmethod
    def orbit_velocity(mass_central:float, distance:float) -> pygame.math.Vector2:
        return pygame.math.Vector2(0, (G * mass_central / distance) ** 0.5)

    @staticmethod
    def random(name:str, mass_central:float) -> 'Body':
        pos:pygame.math.Vector2 = pygame.math.Vector2(random.uniform(0.5 * AU_M, 7 * AU_M), 0)
        vel:pygame.math.Vector2 = Body.orbit_velocity(mass_central, pos.length())

        return Body(name, pos, vel, random.uniform(1e5, 1e20), random.randint(1, 3), pygame.Color(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255)))

@dataclass
class FloatRect:
    x: float
    y: float
    width: float
    height: float

    # draws a 1px rect for debugging
    def draw(self, screen:pygame.Surface):
        nw = meters_to_pix(pygame.math.Vector2(self.x, self.y))
        ne = meters_to_pix(pygame.math.Vector2(self.x + self.width, self.y))
        sw = meters_to_pix(pygame.math.Vector2(self.x, self.y + self.height))
        se = meters_to_pix(pygame.math.Vector2(self.x + self.width, self.y + self.height))

        pygame.draw.line(screen, pygame.Color(255, 0, 0), nw, ne)
        pygame.draw.line(screen, pygame.Color(255, 0, 0), ne, se)
        pygame.draw.line(screen, pygame.Color(255, 0, 0), se, sw)
        pygame.draw.line(screen, pygame.Color(255, 0, 0), sw, nw)


@dataclass
class BarnesHutNode:
    boundary: FloatRect
    nw: 'BarnesHutNode | None' = None
    ne: 'BarnesHutNode | None' = None
    sw: 'BarnesHutNode | None' = None
    se: 'BarnesHutNode | None' = None
    body: Body | None = None
    total_mass: float = 0.0
    center_of_mass: pygame.math.Vector2 = pygame.math.Vector2(0, 0)

    @staticmethod
    def is_internal(node: 'BarnesHutNode') -> bool:
        return all([node.nw, node.ne, node.sw, node.se])
    
    @staticmethod
    def is_external(node: 'BarnesHutNode') -> bool:
        return not any([node.nw, node.ne, node.sw, node.se])
    
    @staticmethod
    def get_quadrant(node: 'BarnesHutNode', pos:pygame.math.Vector2) -> Literal['nw', 'ne', 'sw', 'se']:
        mid_x = node.boundary.x + node.boundary.width / 2
        mid_y = node.boundary.y + node.boundary.height / 2

        if pos.x < mid_x and pos.y < mid_y:
            return 'nw'
        elif pos.x >= mid_x and pos.y < mid_y:
            return 'ne'
        elif pos.x < mid_x and pos.y >= mid_y:
            return 'sw'
        else:
            return 'se'

def insert_body_into_barnes_hut_node(node:BarnesHutNode, body:Body):
    # 1. Check if it's an internal node first.
    # Internal nodes have children and body=None.
    # The original code checked 'if not node.body' first, which incorrectly caught internal nodes.
    if BarnesHutNode.is_internal(node):
        node.total_mass += body.mass
        # Update center of mass (weighted average)
        node.center_of_mass = (node.center_of_mass * (node.total_mass - body.mass) + body.pos * body.mass) / node.total_mass

        quadrant = BarnesHutNode.get_quadrant(node, body.pos)

        if not node.nw or not node.ne or not node.sw or not node.se:
            raise ValueError("Internal node missing children.")

        if quadrant == 'nw':
            insert_body_into_barnes_hut_node(node.nw, body)
        elif quadrant == 'ne':
            insert_body_into_barnes_hut_node(node.ne, body)
        elif quadrant == 'sw':
            insert_body_into_barnes_hut_node(node.sw, body)
        else:
            insert_body_into_barnes_hut_node(node.se, body)
    
    # 2. If it's an external node (leaf) and already has a body, we must split it.
    elif node.body:        
        half_w = node.boundary.width / 2
        half_h = node.boundary.height / 2
        x, y = node.boundary.x, node.boundary.y
        
        node.nw = BarnesHutNode(FloatRect(x, y, half_w, half_h))
        node.ne = BarnesHutNode(FloatRect(x + half_w, y, half_w, half_h))
        node.sw = BarnesHutNode(FloatRect(x, y + half_h, half_w, half_h))
        node.se = BarnesHutNode(FloatRect(x + half_w, y + half_h, half_w, half_h))
        
        old_body = node.body
        node.body = None
        
        # Reset mass/com to 0, they will be rebuilt by re-inserting
        node.total_mass = 0
        node.center_of_mass = pygame.math.Vector2(0, 0)

        insert_body_into_barnes_hut_node(node, old_body)
        insert_body_into_barnes_hut_node(node, body)

    # 3. If it's an external node and empty, just place the body here.
    else:
        node.body = body
        node.total_mass = body.mass
        node.center_of_mass = body.pos

def construct_barnes_hut_tree(bodies:list[Body], boundary:FloatRect) -> BarnesHutNode:
    root = BarnesHutNode(boundary=boundary)
    for body in bodies:
        # if its outside the boundary, skip it
        if (body.pos.x < boundary.x or body.pos.x > boundary.x + boundary.width or
            body.pos.y < boundary.y or body.pos.y > boundary.y + boundary.height):
            continue

        insert_body_into_barnes_hut_node(root, body)
    return root

def draw_barnes_hut_tree(node: 'BarnesHutNode', screen: pygame.Surface):
    if BarnesHutNode.is_external(node):
        node.boundary.draw(screen)
        return
    
    if not node.nw or not node.ne or not node.sw or not node.se:
        raise RuntimeError("child doesnt exist")
    
    draw_barnes_hut_tree(node.nw, screen)
    draw_barnes_hut_tree(node.ne, screen)
    draw_barnes_hut_tree(node.sw, screen)
    draw_barnes_hut_tree(node.se, screen)
    

def main():
    pygame.init()

    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Orbit Sim")

    sun_weight = 1.989e30

    bodies: list[Body] = [
        Body("Sun", pygame.math.Vector2(0, 0), pygame.math.Vector2(0, 0), sun_weight, 20, pygame.Color(255, 255, 0)),  # Sun
        Body("Earth", pygame.math.Vector2(AU_M, 0), Body.orbit_velocity(sun_weight, AU_M), 5.972e24, 5, pygame.Color(0, 255, 0)), # Planet
        Body("Mars", pygame.math.Vector2(1.5 * AU_M, 0), Body.orbit_velocity(sun_weight, 1.5 * AU_M), 6.42e23, 7, pygame.Color(255, 0, 0)), # Planet
        Body("Jupiter", pygame.math.Vector2(5 * AU_M, 0), Body.orbit_velocity(sun_weight, 5 * AU_M), 1.9e27, 9, pygame.Color(255, 150, 50)), # Planet
    ]

    for i in range(50):
        bodies.append(
            Body.random(f"asteroid_{i}", sun_weight)
        )

    running = True
    prev_time = time.perf_counter()
    timesteps = 0
    barnes_hut_root = construct_barnes_hut_tree(bodies, FloatRect(-10 * AU_M, -10 * AU_M, 20 * AU_M, 20 * AU_M))
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        dt = timestep

        screen.fill((0, 0, 0))

        if (LOGGING_ENABLED):
            current_time = time.perf_counter()

            if not prev_time:
                prev_time = current_time
            
            delta_time = current_time - prev_time
            prev_time = current_time

            log_str = f"\033[2J\033[H"
            log_str += f"Timestep: {timesteps}\n"
            log_str += f"Time per Step: {delta_time:.4f} seconds\n"

            print(log_str, end='')
            
        barnes_hut_root = construct_barnes_hut_tree(bodies, FloatRect(-20 * AU_M, -20 * AU_M, 40 * AU_M, 40 * AU_M))
        
        if (VISUALIZE_ENABLED):
            draw_barnes_hut_tree(barnes_hut_root, screen)

        for body in bodies:
            #body.update_naeve(bodies, dt)
            body.update(barnes_hut_root, dt)
            body.draw(screen)

        pygame.display.update()

        timesteps += 1

    pygame.quit()

if __name__ == "__main__":
    main()