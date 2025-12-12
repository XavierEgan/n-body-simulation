import pygame
import random

G = 6.67430e-11
SCREEN_SIZE = (800, 600)
AU_M = 1.5e11
ZOOM_FACTOR = .5 # 1 = earth is 100 px from centre of sun
PLANET_SCALE = 2 # multiplier for planet radii, can be uesd to counteract zoom scaling the planets too small

LOGGING_ENABLED = False

timestep = 3600 * 10 # seconds per frame (one hour)

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

    def update(self, bodies:list['Body'], dt:float):
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

        if (LOGGING_ENABLED):
            print(f"{self.name} position: {self.pos}, velocity: {self.vel}")

    
    @staticmethod
    def orbit_velocity(mass_central:float, distance:float) -> pygame.math.Vector2:
        return pygame.math.Vector2(0, (G * mass_central / distance) ** 0.5)

    @staticmethod
    def random(name:str, mass_central:float) -> 'Body':
        pos:pygame.math.Vector2 = pygame.math.Vector2(random.uniform(0.5 * AU_M, 7 * AU_M), 0)
        vel:pygame.math.Vector2 = Body.orbit_velocity(mass_central, pos.length())

        return Body(name, pos, vel, random.uniform(1e5, 1e20), random.randint(1, 3), pygame.Color(random.randint(100, 255), random.randint(100, 255), random.randint(100, 255)))
    

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

    # add 50 random asteroids
    for i in range(500):
        bodies.append(
            Body.random(f"asteroid_{i}", sun_weight)
        )

    running = True
    timesteps = 0
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        dt = timestep

        screen.fill((0, 0, 0))

        if (LOGGING_ENABLED):
            print("\033[2J\033[H", end="")
            print(f"Timesteps Elapsed: {timesteps}, Delta Time: {dt:.4f} s, elapsed time: {timesteps * dt / 3600:.2f} hours")

        for body in bodies:
            body.update(bodies, dt)
            body.draw(screen)

        pygame.display.update()

        timesteps += 1

    pygame.quit()

if __name__ == "__main__":
    main()