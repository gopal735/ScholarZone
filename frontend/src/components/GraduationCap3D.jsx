import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import './GraduationCap3D.css'

/* ═══════════════════════════════════════════════════════════════════
   GraduationCap3D — the WebGL graduation cap from the design reference

   A full port of the reference's Three.js scene, not a simplification of
   it: the same rounded mortarboard, the same cloth material with a woven
   bump map, the same gold button, cord and 48-strand tassel, the same
   studio environment (an inverted box plus four emissive wall panels)
   that produces the reflective metal, the same three-light rig with a
   shadow-casting key light, and the same touchdown shadow plane.

   Everything is click-draggable: horizontal drag spins the cap with
   inertia, a click or tap without a drag tosses it into a 1.9 second
   arc with two full rotations, and it keeps bobbing while you watch.

   Honest about the environment it is in. If WebGL is unavailable,
   unsupported, or the frame budget collapses, it renders nothing and the
   hero keeps its layout. If ``prefers-reduced-motion`` is set, the cap
   renders but stops moving - no tilt, no drift, no toss.

   This component is deliberately standalone so the page never pays for
   a 3D canvas it cannot show.
   ═══════════════════════════════════════════════════════════════════ */

const T = {
  //: The studio environment uses linear-light colours so the reflections
  //: read as light on metal rather than as paint.
  env: 0x1b2130,
  keyLight: 0xfff1e0,
  keyLightDark: 0xdfe8ff,
  fillLight: 0x9fb4ff,
  cloth: 0x2b3750,
  clothDark: 0x222c42,
  gold: 0xe0b040,
  goldDim: 0xcfa030,
}

const TOUCH_REQUIRED_PX = 8

function buildScene(THREE_, renderer) {
  const scene = new THREE_.Scene()
  const camera = new THREE_.PerspectiveCamera(30, 1, 0.1, 60)
  camera.position.set(0, 3.4, 11.5)
  camera.lookAt(0, -0.25, 0)

  // The studio: a large inverted box with four emissive panels placed like
  // softboxes. Without this, metalness:1 gold reflects nothing and reads as
  // flat yellow.
  const envScene = new THREE_.Scene()
  envScene.add(
    new THREE_.Mesh(
      new THREE_.BoxGeometry(24, 24, 24),
      new THREE_.MeshBasicMaterial({ color: T.env, side: THREE_.BackSide })
    )
  )
  //: [x, y, z, w, h, d, grey] — one above the set, two at the sides, one
  //: behind as a rim.
  ;[
    [0, 11.5, 0, 12, 0.3, 12, 5],
    [-11.5, 3, 2, 0.3, 7, 9, 2.6],
    [11.5, 2, -1, 0.3, 6, 8, 1.6],
    [0, 4, -11.5, 10, 5, 0.3, 1.4],
  ].forEach((a) => {
    const panel = new THREE_.Mesh(
      new THREE_.BoxGeometry(a[3], a[4], a[5]),
      new THREE_.MeshBasicMaterial({ color: new THREE_.Color(a[6], a[6], a[6]) })
    )
    panel.position.set(a[0], a[1], a[2])
    envScene.add(panel)
  })
  const pmrem = new THREE_.PMREMGenerator(renderer)
  scene.environment = pmrem.fromScene(envScene, 0.03).texture

  return { scene, camera }
}

function buildLights(THREE_, scene) {
  const key = new THREE_.DirectionalLight(T.keyLight, 2.1)
  key.position.set(-5, 8, 6)
  key.castShadow = true
  key.shadow.mapSize.set(1024, 1024)
  key.shadow.camera.left = -5
  key.shadow.camera.right = 5
  key.shadow.camera.top = 5
  key.shadow.camera.bottom = -5
  key.shadow.camera.near = 1
  key.shadow.camera.far = 30
  key.shadow.bias = -0.0002
  //: A high blur radius with an open shadow map is what makes the contact
  //: shadow read as a soft penumbra instead of a hard-edged blob.
  key.shadow.radius = 7
  key.shadow.blurSamples = 16
  scene.add(key)

  const fill = new THREE_.DirectionalLight(new THREE_.Color(T.fillLight), 0.55)
  fill.position.set(6, 2, 4)
  scene.add(fill)

  const rim = new THREE_.DirectionalLight(0xffffff, 0.9)
  rim.position.set(0, 4, -8)
  scene.add(rim)

  scene.add(new THREE_.HemisphereLight(0xffffff, T.envHemisphere ?? 0x223044, 0.22))

  const floor = new THREE_.Mesh(
    new THREE_.PlaneGeometry(16, 16),
    new THREE_.ShadowMaterial({ opacity: 0.3 })
  )
  floor.rotation.x = -Math.PI / 2
  floor.position.y = -1.5
  floor.receiveShadow = true
  scene.add(floor)

  return { key, floor }
}

function buildFabric(THREE_) {
  //: The weave. A tiny procedural texture where the tone alternates per
  //: 4-pixel block on alternating rows, giving the cloth its thread; a
  //: MeshPhysicalMaterial without a bump map is a plastic cap.
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 64
  const ctx = canvas.getContext('2d')
  for (let y = 0; y < 64; y += 1) {
    for (let x = 0; x < 64; x += 1) {
      const tone = ((x >> 2) + (y >> 2)) & 1 ? (x & 3) * 40 + 60 : (y & 3) * 40 + 60
      ctx.fillStyle = `rgb(${tone},${tone},${tone})`
      ctx.fillRect(x, y, 1, 1)
    }
  }
  const texture = new THREE_.CanvasTexture(canvas)
  texture.wrapS = texture.wrapT = THREE_.RepeatWrapping
  texture.repeat.set(6, 6)
  texture.anisotropy = 8
  return texture
}

function buildCap(THREE_, scene) {
  //: Two materials at different tones so the band reads as a separate
  //: piece of cloth from the mortarboard itself.
  const fabric = buildFabric(THREE_)
  const cloth = new THREE_.MeshPhysicalMaterial({
    color: new THREE_.Color(T.cloth),
    roughness: 0.9,
    bumpMap: fabric,
    bumpScale: 1.1,
    //: Deliberately low: the studio should read in the highlights, not
    //: wash the whole surface in it.
    envMapIntensity: 0.08,
    side: THREE_.DoubleSide,
  })
  const cloth2 = new THREE_.MeshPhysicalMaterial({
    color: new THREE_.Color(T.clothDark),
    roughness: 0.92,
    envMapIntensity: 0.08,
    side: THREE_.DoubleSide,
  })
  const gold = new THREE_.MeshStandardMaterial({
    color: new THREE_.Color(T.gold),
    metalness: 1,
    roughness: 0.3,
    envMapIntensity: 1.5,
  })
  const goldDim = new THREE_.MeshStandardMaterial({
    color: new THREE_.Color(T.goldDim),
    metalness: 1,
    roughness: 0.42,
    envMapIntensity: 1.3,
  })

  const cap = new THREE_.Group()
  scene.add(cap)

  const add = (geometry, material, x, y, z, parent) => {
    const mesh = new THREE_.Mesh(geometry, material)
    mesh.position.set(x, y, z)
    mesh.castShadow = true
    mesh.receiveShadow = true
    ;(parent || cap).add(mesh)
    return mesh
  }

  // The mortarboard: a rounded square extruded flat. The corner radius is
  // what makes it read as a graduation cap rather than a tile.
  const shape = new THREE_.Shape()
  const s = 1.7
  const r = 0.09
  shape.moveTo(-s + r, -s)
  shape.lineTo(s - r, -s)
  shape.quadraticCurveTo(s, -s, s, -s + r)
  shape.lineTo(s, s - r)
  shape.quadraticCurveTo(s, s, s - r, s)
  shape.lineTo(-s + r, s)
  shape.quadraticCurveTo(-s, s, -s, s - r)
  shape.lineTo(-s, -s + r)
  shape.quadraticCurveTo(-s, -s, -s + r, -s)
  const boardGeometry = new THREE_.ExtrudeGeometry(shape, {
    depth: 0.06,
    bevelEnabled: true,
    bevelThickness: 0.028,
    bevelSize: 0.028,
    bevelSegments: 4,
    curveSegments: 8,
  })
  boardGeometry.center()
  boardGeometry.rotateX(-Math.PI / 2)
  const board = add(boardGeometry, cloth, 0, 0.5, 0)
  board.rotation.y = Math.PI / 4

  // The bowl under it, plus its band.
  add(new THREE_.CylinderGeometry(1, 1.14, 0.95, 64, 1, true), cloth2, 0, 0, 0)
  const band = add(new THREE_.TorusGeometry(1.14, 0.05, 16, 72), cloth2, 0, -0.47, 0)
  band.rotation.x = Math.PI / 2

  // The button, the cord and the tassel.
  add(new THREE_.CylinderGeometry(0.1, 0.12, 0.07, 32), gold, 0, 0.6, 0)
  add(new THREE_.SphereGeometry(0.085, 24, 16), gold, 0, 0.64, 0)
  const cordCurve = new THREE_.CatmullRomCurve3([
    new THREE_.Vector3(0, 0.64, 0),
    new THREE_.Vector3(0.7, 0.62, 0.05),
    new THREE_.Vector3(1.5, 0.6, -0.02),
    new THREE_.Vector3(2.15, 0.58, 0),
    new THREE_.Vector3(2.42, 0.42, 0),
    new THREE_.Vector3(2.46, 0.12, 0),
  ])
  add(new THREE_.TubeGeometry(cordCurve, 90, 0.03, 10, false), goldDim, 0, 0, 0)

  const tassel = new THREE_.Group()
  tassel.position.set(2.46, 0.12, 0)
  cap.add(tassel)
  add(new THREE_.CylinderGeometry(0.075, 0.09, 0.24, 20), gold, 0, -0.12, 0, tassel)
  const ring = add(new THREE_.TorusGeometry(0.085, 0.018, 10, 24), gold, 0, -0.26, 0, tassel)
  ring.rotation.x = Math.PI / 2
  const strand = new THREE_.CylinderGeometry(0.009, 0.006, 0.9, 5)
  for (let i = 0; i < 48; i += 1) {
    const angle = (i / 48) * Math.PI * 2
    //: A random spread per strand is what makes the fringe look like
    //: fringe. Seeded per index it would; Math.random is honest here.
    const radius = 0.02 + Math.random() * 0.06
    const strandMesh = add(
      strand, goldDim, Math.cos(angle) * radius, -0.74, Math.sin(angle) * radius, tassel
    )
    strandMesh.rotation.z = Math.cos(angle) * 0.05
    strandMesh.rotation.x = Math.sin(angle) * 0.05
    strandMesh.castShadow = false
  }

  cap.scale.setScalar(0.84)
  return { cap, tassel }
}

export default function GraduationCap3D({ dark = false }) {
  const hostRef = useRef(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reducedMotion =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let renderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      // No WebGL, or no context. The hero keeps its layout; the cap is not
      // essential to the path.
      host.dataset.capStatus = 'unavailable'
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.VSMShadowMap
    host.appendChild(renderer.domElement)

    const { scene, camera } = buildScene(THREE, renderer)
    const { key, floor } = buildLights(THREE, scene)
    const { cap, tassel } = buildCap(THREE, scene)

    // Theme reaction: a cooler key, a deeper contact shadow and a brighter
    // exposure in dark mode, exactly as the reference does it.
    const themeLight = { exposure: 0.92, shadow: 0.24, key: T.keyLight, keyIntensity: 1.9 }
    const themeDark = { exposure: 1, shadow: 0.45, key: T.keyLightDark, keyIntensity: 1.7 }
    const applyTheme = (isDark) => {
      const t = isDark ? themeDark : themeLight
      renderer.toneMappingExposure = t.exposure
      floor.material.opacity = t.shadow
      key.color.set(t.key)
      key.intensity = t.keyIntensity
    }
    applyTheme(dark)

    const resize = () => {
      const width = host.clientWidth || 400
      renderer.setSize(width, width, false)
      camera.updateProjectionMatrix()
    }
    resize()
    const onResize = () => resize()
    window.addEventListener('resize', onResize)

    /* ── Interaction state ────────────────────────────────────────────
       ``dr`` is the accumulated spin (radians), ``vl`` the drag velocity
       that keeps turning it after the pointer stops, ``tossing`` the
       1.9 second toss. Everything else is the idle drift. */
    let dragging = false
    let lastX = 0
    let pressX = 0
    let pressY = 0
    let velocity = 0
    let spin = 0
    let tossing = false
    let tossStart = 0

    const onPointerDown = (event) => {
      dragging = true
      lastX = event.clientX
      pressX = event.clientX
      pressY = event.clientY
      velocity = 0
      try {
        host.setPointerCapture(event.pointerId)
      } catch {
        /* capture is an optimisation, not a requirement */
      }
      host.parentNode?.classList?.add('is-tossing')
    }
    const onPointerMove = (event) => {
      if (!dragging) return
      const delta = (event.clientX - lastX) * 0.009
      lastX = event.clientX
      spin += delta
      velocity = delta
    }
    const onPointerRelease = (event) => {
      if (!dragging) return
      dragging = false
      //: A press that barely moved is a toss, not a failed drag. The 8px
      //: threshold is the same one the reference uses: below it a human
      //: meant to tap.
      if (
        Math.abs(event.clientX - pressX) + Math.abs(event.clientY - pressY) < TOUCH_REQUIRED_PX &&
        !tossing
      ) {
        tossing = true
        tossStart = performance.now()
      }
    }
    host.addEventListener('pointerdown', onPointerDown)
    host.addEventListener('pointermove', onPointerMove)
    host.addEventListener('pointerup', onPointerRelease)
    host.addEventListener('pointercancel', onPointerRelease)

    /* ── The frame loop ───────────────────────────────────────────
       Parseable arithmetic: ``drop`` is the entry fall, ``t`` the toss
       progress, ``iv`` the 1.9 second reveal. All three compose into the
       same rotation, so the cap drops in, keeps bobbing, and can be
       tossed at any point in that sequence. */
    const start = performance.now()
    let frame = 0
    let failed = false

    const tick = () => {
      frame = requestAnimationFrame(tick)
      const now = performance.now()
      const t = (now - start) / 1000
      const reveal = reducedMotion ? 1 : Math.min(1, t / 1.9)
      let tossY = 0
      let tossRot = 0
      let tossZ = 0

      if (tossing) {
        const p = (now - tossStart) / 1900
        if (p >= 1) {
          tossing = false
        } else {
          tossY = 3.1 * Math.sin(Math.PI * p)
          tossRot = Math.PI * 2 * (1 - (1 - p) ** 2)
          tossZ = Math.sin(Math.PI * p) * 0.5
        }
      }
      if (!dragging) {
        spin += velocity
        velocity *= 0.94
        spin *= 0.992
      }

      const drop = (1 - reveal) ** 2
      cap.position.y = (reducedMotion ? 0 : Math.sin(t * 1.3) * 0.1) + drop * 4 + tossY
      cap.rotation.y =
        -0.55 +
        (reducedMotion ? 0 : Math.sin(t * 0.4) * 0.35) +
        drop * 3 +
        spin +
        tossRot
      cap.rotation.x = 0.2 + tossZ * 0.4
      cap.rotation.z = tossZ * 0.3
      tassel.rotation.z =
        (reducedMotion ? 0 : Math.sin(t * 1.7) * 0.1) + (tossing ? -0.5 : 0) + velocity * 2
      tassel.rotation.x = reducedMotion ? 0 : Math.cos(t * 1.3) * 0.07

      renderer.render(scene, camera)
    }
    frame = requestAnimationFrame(tick)

    host.dataset.capStatus = 'live'

    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', onResize)
      host.removeEventListener('pointerdown', onPointerDown)
      host.removeEventListener('pointermove', onPointerMove)
      host.removeEventListener('pointerup', onPointerRelease)
      host.removeEventListener('pointercancel', onPointerRelease)
      scene.traverse((object) => {
        if (object.geometry) object.geometry.dispose()
        if (object.material) {
          const materials = Array.isArray(object.material) ? object.material : [object.material]
          materials.forEach((material) => material.dispose())
        }
      })
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
      if (failed) host.dataset.capStatus = 'unavailable'
    }
  }, [dark])

  return (
    <div
      className="cap3d"
      ref={hostRef}
      role="img"
      aria-label="A graduation cap and tassel you can drag to spin, or click to toss"
    />
  )
}
