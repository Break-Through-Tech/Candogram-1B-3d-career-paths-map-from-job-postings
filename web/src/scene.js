import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

// One color per seniority rank (Student → Executive).
export const SENIORITY_COLORS = ['#7dd3fc', '#34d399', '#facc15', '#fb923c', '#f472b6']

const DIM_COLOR = new THREE.Color('#3a4150')
const POINT_RADIUS = 0.09

/**
 * Renders jobs as an instanced sphere cloud with orbit controls, hover and
 * click picking, and a highlighted career path polyline.
 */
export function createScene(container, jobs, { onHover, onSelect }) {
  const renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  container.appendChild(renderer.domElement)

  const scene = new THREE.Scene()
  scene.background = new THREE.Color('#0b0f17')

  const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500)
  camera.position.set(14, 8, 16)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true

  scene.add(new THREE.AmbientLight('#ffffff', 0.6))
  const sun = new THREE.DirectionalLight('#ffffff', 1.2)
  sun.position.set(10, 20, 10)
  scene.add(sun)

  const grid = new THREE.GridHelper(24, 24, '#1f2937', '#151b26')
  grid.position.y = -4.6
  scene.add(grid)

  // Center the cloud on the orbit target.
  const center = new THREE.Vector3()
  for (const job of jobs) center.add(new THREE.Vector3(job.x, job.y, job.z))
  center.divideScalar(jobs.length || 1)
  controls.target.copy(center)

  const geometry = new THREE.SphereGeometry(POINT_RADIUS, 12, 12)
  const material = new THREE.MeshStandardMaterial({ roughness: 0.5 })
  const mesh = new THREE.InstancedMesh(geometry, material, jobs.length)
  const matrix = new THREE.Matrix4()
  const baseColors = jobs.map((job) => new THREE.Color(SENIORITY_COLORS[job.seniority_rank]))
  const visible = jobs.map(() => true)
  jobs.forEach((job, i) => {
    matrix.makeTranslation(job.x, job.y, job.z)
    mesh.setMatrixAt(i, matrix)
    mesh.setColorAt(i, baseColors[i])
  })
  scene.add(mesh)

  const pathGroup = new THREE.Group()
  scene.add(pathGroup)

  // Picking
  const raycaster = new THREE.Raycaster()
  const pointer = new THREE.Vector2()
  let hovered = -1

  function pick(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(pointer, camera)
    const hit = raycaster.intersectObject(mesh).find((entry) => visible[entry.instanceId])
    return hit ? hit.instanceId : -1
  }

  renderer.domElement.addEventListener('pointermove', (event) => {
    const index = pick(event)
    if (index === hovered) return
    hovered = index
    renderer.domElement.style.cursor = index >= 0 ? 'pointer' : ''
    onHover(index >= 0 ? jobs[index] : null, event)
  })

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

  /** Dim everything except `path`, draw a line through it, and focus it. */
  function updateInstances(path) {
    const onPath = new Set(path)
    jobs.forEach((job, i) => {
      const scale = visible[i] ? (onPath.has(job) ? 2.2 : 1) : 0
      matrix.makeScale(scale, scale, scale).setPosition(job.x, job.y, job.z)
      mesh.setMatrixAt(i, matrix)
      mesh.setColorAt(i, path.length && !onPath.has(job) ? DIM_COLOR : baseColors[i])
    })
    mesh.instanceMatrix.needsUpdate = true
    mesh.instanceColor.needsUpdate = true
  }

  function showPath(path, focus = true) {
    pathGroup.clear()
    updateInstances(path)

    if (path.length > 1) {
      const points = path.map((job) => new THREE.Vector3(job.x, job.y, job.z))
      const curve = new THREE.CatmullRomCurve3(points, false, 'centripetal')
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(curve, path.length * 24, 0.035, 8, false),
        new THREE.MeshBasicMaterial({ color: '#ffffff', transparent: true, opacity: 0.85 }),
      )
      pathGroup.add(tube)
    }
    if (path.length && focus) {
      const box = new THREE.Box3().setFromPoints(path.map((j) => new THREE.Vector3(j.x, j.y, j.z)))
      box.getCenter(controls.target)
    }
  }

  function setVisibleJobs(visibleJobs) {
    const visibleSet = new Set(visibleJobs)
    jobs.forEach((job, i) => { visible[i] = visibleSet.has(job) })
    updateInstances([])
  }

  function resize() {
    const { clientWidth: w, clientHeight: h } = container
    renderer.setSize(w, h)
    camera.aspect = w / h
    camera.updateProjectionMatrix()
  }
  new ResizeObserver(resize).observe(container)
  resize()

  renderer.setAnimationLoop(() => {
    controls.update()
    renderer.render(scene, camera)
  })

  return { showPath, setVisibleJobs }
}
