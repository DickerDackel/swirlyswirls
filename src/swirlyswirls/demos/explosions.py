import pygame
import tinyecs as ecs
import tinyecs.components as ecsc
import swirlyswirls as sw
import swirlyswirls.compsys as swcs
import swirlyswirls.particles
import swirlyswirls.zones

from functools import partial

from pgcooldown import Cooldown, LerpThing
from pygame import Vector2
from pygamehelpers.framework import GameState
from rpeasings import out_quint


class Demo(GameState):
    def __init__(self, app, persist, parent=None):
        super().__init__(app, persist, parent=parent)

        self.title = 'Bubble Explosions'
        self.cache = {}
        self.group = sw.ReversedGroup()
        self.momentum = False
        self.cooldown = Cooldown(5, cold=True)

        self.label = self.persist.font.render('Press space to toggle momentum', True, 'white')

        self.ecs_register_systems()

        self.emitters = [
            partial(
                sw.Emitter,
                zone=swirlyswirls.zones.ZoneCircle(r0=0, r1=16),
                particle_factory=partial(self.explosion_particle_factory,
                                         group=self.group, cache=self.cache,
                                         max_size=16)
            ),
            partial(
                sw.Emitter,
                zone=swirlyswirls.zones.ZoneCircle(r0=0, r1=32),
                particle_factory=partial(self.explosion_particle_factory,
                                         group=self.group, cache=self.cache,
                                         max_size=32)
            ),
            partial(
                sw.Emitter,
                zone=swirlyswirls.zones.ZoneCircle(r0=0, r1=64),
                particle_factory=partial(self.explosion_particle_factory,
                                         group=self.group, cache=self.cache,
                                         max_size=64)
            ),
        ]

    def reset(self, persist=None):
        """Reset settings when re-running."""
        super().reset(persist=persist)
        ...

    def dispatch_event(self, e):
        """Handle user events"""
        super().dispatch_event(e)

        match e.type:
            case pygame.KEYDOWN if e.key == pygame.K_SPACE:
                self.momentum = not self.momentum
                if self.momentum:
                    ecs.add_system(ecsc.momentum_system, 'momentum', 'position')
                else:
                    ecs.remove_system(ecsc.momentum_system)

    def update(self, dt):
        """Update frame by delta time dt."""

        if self.cooldown.cold:
            self.cooldown.reset()
            step = self.app.rect.width // 6
            for i in range(3):
                x = step + i * 2 * step
                pos = (x, self.app.rect.centery)
                self.launch_emitter(pos, self.emitters[i])

        ecs.run_all_systems(dt)

        self.group.update(dt)

        sprites = len(self.group.sprites())
        c = len(list(self.cache.keys()))
        pygame.display.set_caption(f'{self.title} - time={pygame.time.get_ticks()/1000:.2f}  fps={self.app.clock.get_fps():.2f}  {sprites=}  {c=}')

    def draw(self, screen):
        """Draw current frame to surface screen."""

        screen.fill('black')
        screen.blit(self.label, (5, 5))

        self.group.draw(screen)

        pygame.display.flip()

    @staticmethod
    def draw_box_bubble(surface, r, t, base_color, highlight_color):
        rect = pygame.Rect(0, 0, 2 * r, 2 * r)

        pygame.draw.rect(surface, highlight_color, rect, width=2)
        rect.centerx += 1
        rect.centery -= 1
        pygame.draw.rect(surface, base_color, rect)

    @staticmethod
    def ecs_register_systems():
        ecs.add_system(ecsc.lifetime_system, 'lifetime')
        ecs.add_system(swcs.emitter_system, 'emitter', 'position')
        ecs.add_system(swcs.particle_rsai_system, 'particle', 'rsai')
        ecs.add_system(ecsc.sprite_system, 'sprite', 'position')

    @staticmethod
    def launch_emitter(pos, emitter):
        e = ecs.create_entity()
        ecs.add_component(e, 'emitter', emitter(ept=LerpThing(2, 5, 1)))
        ecs.add_component(e, 'position', Vector2(pos))
        ecs.add_component(e, 'lifetime', Cooldown(1))

    @staticmethod
    def explosion_particle_factory(t, position, momentum, group, cache, max_size):
        e = ecs.create_entity()

        def image_factory(rotate, scale, alpha):
            size = max_size * scale
            return swirlyswirls.particles.firesquabble_image_factory(size, alpha)

        rsai = ecsc.RSAImage(None, image_factory=image_factory)

        p = swcs.Particle(scale=LerpThing(1 / 4, 1, 0.75, ease=out_quint),
                          alpha=LerpThing(255, 0, 0.75, ease=out_quint))

        ecs.add_component(e, 'rsai', rsai)
        ecs.add_component(e, 'particle', p)
        ecs.add_component(e, 'lifetime', Cooldown(0.75))
        ecs.add_component(e, 'sprite', ecsc.EVSprite(rsai, group))
        ecs.add_component(e, 'position', Vector2(position))
        ecs.add_component(e, 'momentum', momentum * 3)
        ecs.add_component(e, 'cache', cache)
