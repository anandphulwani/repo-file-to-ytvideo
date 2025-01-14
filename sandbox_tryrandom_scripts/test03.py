# Example of animating text with Pygame (simplified)
import pygame

pygame.init()
screen = pygame.display.set_mode((640, 480))
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 55)
text = font.render('Hello, World!', True, (0, 128, 0))

x = 0
y = 240

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill((255, 255, 255))
    screen.blit(text, (x, y))
    x += 1  # Move text horizontally

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
