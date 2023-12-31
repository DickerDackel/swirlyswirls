import tinyecs as ecs
import swirlyswirls.zones

from dataclasses import dataclass, InitVar
from itertools import cycle

from pgcooldown import Cooldown, LerpThing
from pygame import Vector2

_lerp     = lambda a, b, t: (1 - t) * a + b * t


@dataclass(kw_only=True)
class Emitter:
    """Data for the `emitter_system`.

    See `emitter_system` for usage.

    Attributes
    ----------
    ept: pgcooldown.LerpThing
        `ept` is short for "Emits per Tick", and it describes how many entities
        to launch at every heartbeat, and over what time.

        The LerpThing gets the following parameters:

            duration: [Cooldown | float] = 0
                The duration over that the emitter emits.

                This is distinct from lifetime, since it might be necessary to
                access the emitter after it has finished emitting (e.g. for
                particles to kill their siblings).

            vt0:
                Emits per tick at the start of the emitter.
            vt1:
                Emits per tick at the end of `duration`

            ease: callable = lambda x: x
                An optional ease function put over the `t` of the lerp.

                E.g. if you want to emit a big burst and then quickly tickle
                down for the remainder of the time.

    tick : float = 0.1
        The heartbeat of the emitter.

    ticklist: list[float]
        Change the heartbeat every time it fires.  This list cycles.  Use it
        for bullet stacking in patterns, e.g.

            [5/60, 5/60, 5/60, 1]


    total_emits: int = None
        if set, limit the total number of emits.  If the emitter is exhausted,
        the entity removes itself.

        Lifetime does still need to be controlled by a `lifetime` component.
        Reaching `total_emits` will not terminate the emitter object itself.

    zone : callable
        The zone function.  See `emitter_system` for details.

    particle_factory: callable
        A callback to create a particle.

        This function is expected to receive the following parameters:

            t: float
                The normalized lifetime of the emitter (e.g. to shrink
                particle size relative to the age of the emitter)
            position: Vector2
                The position where the particle is emitted
            momentum: Vector2
                The momentum of the particle

    inherit_momentum: 0
        Which momentum to inherit:
            0: no momentum
            1: emitter only
            2: zone only
            3: emitter + zone (default)

    """
    ept: LerpThing
    tick: InitVar[float] = 0.1
    ticklist: InitVar[list[float]]
    total_emits: InitVar[int] = None
    zone: swirlyswirls.zones.Zone
    particle_factory: callable
    inherit_momentum: int = 3

    def __post_init__(self, tick, ticklist, total_emits):
        self.tick = Cooldown(tick, cold=True)
        self.ticker = cycle(ticklist) if ticklist else cycle([tick])
        self.remaining = total_emits if total_emits is not None else -1


def emitter_system(dt, eid, emitter, position):
    """The management system for Emitter entities.

    The emitter system isn't much more than a heartbeat.

    It's center configuration is the emitter object:

    On each `tick`, a number of entities are launched until `total_emits` is
    reached or `duration` has passed.

    For every entity, the `emiter.zone` function is called without parameters.
    It is expected to return

        1. a `position` Vector2,
        2. a `momentum` Vector2.

    The `position` vector is expected to be relative to the `zone` anchor, so
    the `position` of the emitter needs to be added to it.

    This system doesn't require a momentum, but it checks if one is available.
    The momentum of the particle is constructed from the momentum the zone
    provided, and the momentum of the emitter, depending on
    `emitter.inherit_momentum` (see `swirlyswirls.Emitter`).

    Both, `position` and `momentum` are passed into the `emitter.emit`
    function, which is then expecte to create a particle entity with all
    necessary components.

    If `emitter.duration` (see `swirlyswirls.Emitter`) is non-zero and
    positive, emits are lerped between `vt0` and `vt1` (see
    `pgcooldown.LerpThing`) based on the length of the `duration`.  If
    `duration` is zero, the working time for the emitter is infinite and only
    `vt0` is used.

    Parameters
    ----------
    emitter : swirlyswirl.emitter.Emitter
        Management data for the `emitter_system`.
    position: Vector2
        Position of the emitter

    Returns
    -------
    None

    """

    if emitter.tick.hot:
        return

    emitter.tick.reset(next(emitter.ticker))

    if emitter.remaining == 0:
        return

    ept = emitter.ept
    # If we have a valid duration and it's cold, simply return
    # If we have a valid duration that's hot, get t from it
    # If duration is not valid, try to derive it from lifetime
    # Finally, if all fails, default t to 0
    if ept.duration.duration:
        if ept.duration.cold:
            return
        else:
            t = ept.duration.normalized
    else:
        if ecs.eid_has(eid, 'lifetime'):
            t = ecs.comp_of_eid(eid, 'lifetime').normalized
        else:
            t = 0

    emits = int(ept())

    if emitter.remaining > 0:
        emits = min(emits, emitter.remaining)
        emitter.remaining -= emits

    if emitter.inherit_momentum & 1 and ecs.eid_has(eid, 'momentum'):
        e_momentum = ecs.comp_of_eid(eid, 'momentum')
    else:
        e_momentum = Vector2(0, 0)

    for i in range(emits):
        z_position, z_momentum = emitter.zone.emit(t)

        momentum = Vector2()
        if emitter.inherit_momentum & 1:
            momentum += e_momentum
        if emitter.inherit_momentum & 2:
            momentum += z_momentum

        emitter.particle_factory(t=t, position=position + z_position, momentum=momentum)


@dataclass(kw_only=True)
class Particle:
    """Data to manage the lifecycle of a single particle.

    See `particle_system` for details.


    Parameters
    ----------
    rotate: LerpThing
        Management of rotation

    scale: LerpThing
        Management of scaling

    alpha: LerpThing
        Management of alpha

    """
    rotate: LerpThing = None
    scale: LerpThing = None
    alpha: LerpThing = None


def particle_system(dt, eid, particle):
    """This is a nop, all lerp things handle their updates automagically"""
    pass


def particle_rsai_system(dt, eid, particle, rsai):
    """Bind particle information to an rsai.

    An `RSAImage` manages rotation, scaling, alpha of a (optionally dynamically
    generated image.  See `tinyecs.compsys.RSAImage`.

    A Particle manages rotation, scale, alpha of a Particle.

    `particle_rsai_system` glues these two together, pushing the `particle`
    information into the `rsai`

    Parameters
    ----------
    particle: swirlyswirls.Particle
        The particle component.

    rsai: tinyecs.compsys.RSAImage
        The image component

    """
    rsai.lock = True
    if particle.rotate is not None: rsai.rotate = particle.rotate.v
    if particle.scale is not None: rsai.scale = particle.scale.v
    if particle.alpha is not None: rsai.alpha = particle.alpha.v
    rsai.lock = False


def container_system(dt, eid, container, position, momentum, sprite):
    """A system to make a sprite bonce off the edges of the screen.

    This is not of use for actual programs, but it's a nice example of a custom
    component.  It can still be used in test programs if you need to manage
    your sprites on screen.

    Parameters
    ----------
    container : pygame.Rect
        The bounding box for the sprites
    position: pygame.Vector2
        World position and state of the sprite.  If a wall is hit, the position
        will be reset to inside the container.
    momentum
        The momentum of the sprite.  On wall hit, it is inversed on the
        collision axis.
    sprite : tinyecs.components.ESprite
        The visualization of the entity, a.k.a. the sprite to bounce around.

    Returns
    -------
    None

    """
    if sprite.rect.left < container.left and momentum.x < 0:
        momentum.x = -momentum.x
        position.x += -2 * sprite.rect.left
    elif sprite.rect.right > container.right and momentum.x > 0:
        momentum.x = -momentum.x
        position.x += 2 * (container.width - sprite.rect.right)

    if sprite.rect.top < container.top and momentum.x < 0:
        momentum.y = -momentum.y
        position.y += -2 * sprite.rect.top
    elif sprite.rect.bottom > container.bottom and momentum.y > 0:
        momentum.y = -momentum.y
        position.y += 2 * (container.height - sprite.rect.bottom)
