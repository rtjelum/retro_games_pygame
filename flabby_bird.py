import pygame
import sys

# --- Configuration & Constants ---
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
GRAVITY = 0.25
FLAP_STRENGTH = -6
PIPE_SPEED = 3
PIPE_GAP = 150
PIPE_FREQUENCY = 1500  # Milliseconds

# Colors
WHITE = (255, 255, 255)
SKY_BLUE = (135, 206, 235)
BIRD_YELLOW = (255, 255, 0)
PIPE_GREEN = (34, 139, 34)

class Bird:
    def __init__(self):
        self.x = 50
        self.y = SCREEN_HEIGHT // 2
        self.velocity = 0
        self.rect = pygame.Rect(self.x, self.y, 34, 24)

    def update(self):
        self.velocity += GRAVITY
        self.y += self.velocity
        self.rect.y = self.y

    def flap(self):
        self.velocity = FLAP_STRENGTH

    def draw(self, screen):
        pygame.draw.rect(screen, BIRD_YELLOW, self.rect)

class Pipe:
    def __init__(self, x):
        self.x = x
        self.gap_y = random.randint(100, SCREEN_HEIGHT - 100 - PIPE_GAP)
        self.width = 50
        self.passed = False
        
        # Top and Bottom rectangles
        self.top_rect = pygame.Rect(self.x, 0, self.width, self.gap_y)
        self.bottom_rect = pygame.Rect(self.x, self.gap_y + PIPE_GAP, self.width, SCREEN_HEIGHT)

    def update(self):
        self.x -= PIPE_SPEED
        self.top_rect.x = self.x
        self.bottom_rect.x = self.x

    def draw(self, screen):
        pygame.draw.rect(screen, PIPE_GREEN, self.top_rect)
        pygame.draw.rect(screen, PIPE_GREEN, self.bottom_rect)

import random # Moved import to top level

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Flappy Bird Pygame")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 32)

    # Game State
    bird = Bird()
    pipes = []
    score = 0
    last_pipe_time = pygame.time.get_ticks()
    game_active = True

    while True:
        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if game_active:
                        bird.flap()
                    else:
                        # Reset Game
                        bird = Bird()
                        pipes = []
                        score = 0
                        game_active = True

        if game_active:
            # 2. Update Logic
            bird.update()

            # Spawn pipes
            current_time = pygame.time.get_ticks()
            if current_time - last_pipe_time > PIPE_FREQUENCY:
                pipes.append(Pipe(SCREEN_WIDTH))
                last_pipe_time = current_time

            for pipe in pipes[:]:
                pipe.update()
                
                # Collision Detection
                if bird.rect.colliderect(pipe.top_rect) or bird.rect.colliderect(pipe.bottom_rect):
                    game_active = False
                
                # Scoring
                if not pipe.passed and pipe.x + pipe.width < bird.x:
                    score += 1
                    pipe.passed = True

                # Remove off-screen pipes
                if pipe.x + pipe.width < 0:
                    pipes.remove(pipe)

            # Floor/Ceiling collision
            if bird.y <= 0 or bird.y >= SCREEN_HEIGHT:
                game_active = False

            # 3. Drawing
            screen.fill(SKY_BLUE)
            bird.draw(screen)
            for pipe in pipes:
                pipe.draw(screen)
            
            # Display Score
            score_surface = font.render(f"Score: {score}", True, WHITE)
            screen.blit(score_surface, (10, 10))

        else:
            # Game Over Screen
            over_surface = font.render("GAME OVER", True, WHITE)
            restart_surface = font.render("Press SPACE to Restart", True, WHITE)
            screen.blit(over_surface, (SCREEN_WIDTH//2 - 80, SCREEN_HEIGHT//2 - 50))
            screen.blit(restart_surface, (SCREEN_WIDTH//2 - 140, SCREEN_HEIGHT//2 + 10))

        pygame.display.update()
        clock.tick(60)

if __name__ == "__main__":
    main()
