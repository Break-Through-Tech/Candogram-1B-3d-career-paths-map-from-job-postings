import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'

// One color per seniority rank (Student → Executive), cool to warm like star temperatures.
export const SENIORITY_COLORS = ['#67e8f9', '#86efac', '#fde047', '#fb923c', '#f472b6']

const POINT_RADIUS = 0.085
const DIM_FACTOR = 0.09 // faded but still visible; below the bloom threshold
const HIDDEN_COLOR = new THREE.Color('#141426')
const PATH_COLOR = new THREE.Color('#e9d5ff')

const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** A soft round sprite, used for background stars and the hover halo. */
function glowTexture({ ring = false } = {}) {
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  if (ring) {
    gradient.addColorStop(0.55, 'rgba(255,255,255,0)')
    gradient.addColorStop(0.68, 'rgba(255,255,255,0.95)')
    gradient.addColorStop(0.78, 'rgba(255,255,255,0)')
  } else {
    gradient.addColorStop(0, 'rgba(255,255,255,1)')
    gradient.addColorStop(0.25, 'rgba(255,255,255,0.6)')
    gradient.addColorStop(1, 'rgba(255,255,255,0)')
  }
  ctx.fillStyle = gradient
  ctx.fillRect(0, 0, size, size)
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

/** Painted nebula used as the scene background. */
function nebulaTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 1600
  canvas.height = 1000
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#05040d'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const clouds = [
    [1150, 260, 620, 'rgba(124, 58, 237, 0.42)'],
    [380, 760, 560, 'rgba(37, 99, 235, 0.30)'],
    [900, 640, 420, 'rgba(219, 39, 119, 0.20)'],
    [250, 180, 380, 'rgba(14, 165, 233, 0.16)'],
    [1450, 850, 420, 'rgba(76, 29, 149, 0.35)'],
  ]
  for (const [x, y, r, color] of clouds) {
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, r)
    gradient.addColorStop(0, color)
    gradient.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, canvas.width, canvas.height)
  }
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

function starfield(count = 3500) {
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)
  const tint = new THREE.Color()
  for (let i = 0; i < count; i++) {
    // Uniform points on a thick shell around the job cloud.
    const r = 60 + Math.random() * 90
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    positions.set([r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta)], i * 3)
    tint.setHSL(0.6 + Math.random() * 0.25, 0.6, 0.6 + Math.random() * 0.4)
    colors.set([tint.r, tint.g, tint.b], i * 3)
  }
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  return new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      size: 0.9,
      map: glowTexture(),
      vertexColors: true,
      transparent: true,
      opacity: 0.8,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    }),
  )
}

/**
 * Renders jobs as a glowing star cloud with orbit controls, hover and click
 * picking, filtering, and an animated career path trail.
 */
export function createScene(container, jobs, { onHover, onSelect, getInsets = () => ({ left: 0, bottom: 0 }) }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = nebulaTexture()

  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500)
  camera.position.set(15, 7, 17)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.autoRotate = !reducedMotion
  controls.autoRotateSpeed = 0.35
  controls.minDistance = 3
  controls.maxDistance = 60

  const stars = starfield()
  scene.add(stars)

  // Center the cloud on the orbit target.
  const center = new THREE.Vector3()
  for (const job of jobs) center.add(new THREE.Vector3(job.x, job.y, job.z))
  center.divideScalar(jobs.length || 1)
  controls.target.copy(center)

  const geometry = new THREE.SphereGeometry(POINT_RADIUS, 14, 14)
  const material = new THREE.MeshBasicMaterial({ toneMapped: false })
  const mesh = new THREE.InstancedMesh(geometry, material, jobs.length)
  const matrix = new THREE.Matrix4()
  const baseColors = jobs.map((job) => new THREE.Color(SENIORITY_COLORS[job.seniority_rank]))
  const scratch = new THREE.Color()
  scene.add(mesh)

  const pathGroup = new THREE.Group()
  scene.add(pathGroup)

  const halo = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: glowTexture({ ring: true }), transparent: true, depthWrite: false, toneMapped: false }),
  )
  halo.scale.setScalar(0.75)
  halo.visible = false
  scene.add(halo)

  // Bloom makes bright stars glow; dimmed stars sit under the threshold.
  const composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.75, 0.5, 0.24)
  composer.addPass(bloom)
  composer.addPass(new OutputPass())

  let visible = jobs.map(() => true)
  let path = []
  let curve = null
  let comet = null

  /** Recompute every point's size and color from the filter and path. */
  function redraw() {
    const onPath = new Set(path)
    jobs.forEach((job, i) => {
      let scale = 1
      let color = baseColors[i]
      if (onPath.has(job)) scale = 2
      else if (!visible[i]) { scale = 0.5; color = HIDDEN_COLOR }
      else if (path.length) { scale = 0.45; color = scratch.copy(baseColors[i]).multiplyScalar(DIM_FACTOR) }
      matrix.makeScale(scale, scale, scale).setPosition(job.x, job.y, job.z)
      mesh.setMatrixAt(i, matrix)
      mesh.setColorAt(i, color)
    })
    mesh.instanceMatrix.needsUpdate = true
    mesh.instanceColor.needsUpdate = true
  }
  redraw()

  // --- Camera flights ---------------------------------------------------------

  let flight = null // { target, position } the camera eases toward

  /** Camera distance that fits a sphere of `radius` on screen, for either orientation. */
  function fitDistance(radius) {
    const vFov = THREE.MathUtils.degToRad(camera.fov)
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect)
    return (radius / Math.sin(Math.min(vFov, hFov) / 2)) * 1.25
  }

  function flyTo(target, distance) {
    const direction = camera.position.clone().sub(controls.target).normalize()
    flight = { target: target.clone(), position: target.clone().add(direction.multiplyScalar(distance)) }
  }

  controls.addEventListener('start', () => {
    flight = null
    controls.autoRotate = false
  })

  // --- Picking ---------------------------------------------------------------

  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  let hovered = -1

  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObject(mesh).find((h) => visible[h.instanceId] || path.includes(jobs[h.instanceId]))
    return hit ? hit.instanceId : -1
  }

  function setHovered(index, event) {
    if (index === hovered) return
    hovered = index
    renderer.domElement.style.cursor = index >= 0 ? 'pointer' : ''
    halo.visible = index >= 0
    if (index >= 0) {
      const job = jobs[index]
      halo.position.set(job.x, job.y, job.z)
      halo.material.color.copy(baseColors[index])
    }
    onHover(index >= 0 ? jobs[index] : null, event)
  }

  renderer.domElement.addEventListener('pointermove', (event) => setHovered(pick(event), event))
  renderer.domElement.addEventListener('pointerleave', () => setHovered(-1))

  // Distinguish clicks from orbit drags.
  let downAt = null
  renderer.domElement.addEventListener('pointerdown', (e) => (downAt = [e.clientX, e.clientY]))
  renderer.domElement.addEventListener('pointerup', (event) => {
    if (!downAt) return
    const moved = Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1])
    downAt = null
    if (moved > 4) return
    const index = pick(event)
    onSelect(index >= 0 ? jobs[index] : null)
  })

  // --- Public API --------------------------------------------------------------

  /** Show only jobs where `isVisible(job)` is true; the rest fade out. */
  function setFilter(isVisible) {
    visible = jobs.map(isVisible)
    redraw()
  }

  /** Dim everything except `nextPath`, draw a glowing trail through it, and fly to it. */
  function showPath(nextPath) {
    const changed = nextPath.length !== path.length || nextPath.some((job, i) => job !== path[i])
    path = nextPath
    redraw()
    if (!changed) return

    pathGroup.clear()
    curve = null
    comet = null
    if (path.length > 1) {
      const points = path.map((job) => new THREE.Vector3(job.x, job.y, job.z))
      curve = new THREE.CatmullRomCurve3(points, false, 'centripetal')
      const segments = path.length * 32
      pathGroup.add(
        new THREE.Mesh(
          new THREE.TubeGeometry(curve, segments, 0.022, 8, false),
          new THREE.MeshBasicMaterial({ color: PATH_COLOR, toneMapped: false }),
        ),
        new THREE.Mesh(
          new THREE.TubeGeometry(curve, segments, 0.09, 12, false),
          new THREE.MeshBasicMaterial({
            color: '#a78bfa',
            transparent: true,
            opacity: 0.18,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
          }),
        ),
      )
      comet = new THREE.Mesh(
        new THREE.SphereGeometry(0.07, 16, 16),
        new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false }),
      )
      comet.userData.t = 0
      if (!reducedMotion) pathGroup.add(comet)
    }

    if (path.length) {
      const sphere = new THREE.Sphere().setFromPoints(path.map((j) => new THREE.Vector3(j.x, j.y, j.z)))
      controls.autoRotate = false
      flyTo(sphere.center, fitDistance(Math.max(sphere.radius, 3)))
    } else {
      flyTo(center, fitDistance(11))
    }
  }

  function resize() {
    const { clientWidth: w, clientHeight: h } = container
    renderer.setSize(w, h)
    composer.setSize(w, h)
    bloom.resolution.set(w, h)
    // Center the view in the part of the screen the side panel doesn't cover.
    const { left, bottom } = getInsets()
    camera.aspect = w / h
    camera.setViewOffset(w, h, -left / 2, bottom / 2, w, h)
    camera.updateProjectionMatrix()
  }
  new ResizeObserver(resize).observe(container)
  resize()

  const clock = new THREE.Clock()
  renderer.setAnimationLoop(() => {
    const dt = Math.min(clock.getDelta(), 0.1)

    if (flight) {
      const ease = 1 - Math.pow(0.02, dt) // frame-rate independent easing
      controls.target.lerp(flight.target, ease)
      camera.position.lerp(flight.position, ease)
      if (camera.position.distanceTo(flight.position) < 0.05) flight = null
    }

    if (comet && curve && !reducedMotion) {
      comet.userData.t = (comet.userData.t + dt * 0.28) % 1
      curve.getPointAt(comet.userData.t, comet.position)
    }

    if (!reducedMotion) stars.rotation.y += dt * 0.004
    halo.material.rotation += dt * 0.6

    controls.update()
    composer.render()
  })

  return { setFilter, showPath, resize }
}
