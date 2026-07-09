gsap.registerPlugin(ScrollTrigger, MotionPathPlugin);

let mpCtx;

function createMotionTimeline() {
  mpCtx && mpCtx.revert();

  mpCtx = gsap.context(() => {
    const box = document.querySelector(".box");
    const pathSection = document.querySelector(".path-section");
    const initMarker = document.querySelector(".mstop.initial .marker");
    const stops = gsap.utils.toArray(".mstop:not(.initial)");

    if (!initMarker || stops.length === 0) return;

    const psRect = pathSection.getBoundingClientRect();
    const imRect = initMarker.getBoundingClientRect();

    gsap.set(box, {
      top: imRect.top - psRect.top,
      left: imRect.left - psRect.left,
      xPercent: -50,
      yPercent: -50
    });

    const boxRect = box.getBoundingClientRect();

    const points = stops.map((stop) => {
      const marker = stop.querySelector(".marker");
      const r = marker.getBoundingClientRect();
      return {
        x: r.left - boxRect.left,
        y: r.top - boxRect.top
      };
    });

    drawTrace(boxRect, stops);

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".mstop.initial",
        start: "clamp(top center)",
        endTrigger: ".path-end",
        end: "clamp(top center)",
        scrub: 1
      }
    });

    tl.to(box, {
      duration: 1,
      ease: "none",
      motionPath: {
        path: points,
        curviness: 1.5
      }
    });
  });
}

function drawTrace(boxRect, stops) {
  const svg = document.getElementById("path-trace");
  const psRect = document
    .querySelector(".path-section")
    .getBoundingClientRect();

  const pts = [{ x: boxRect.left - psRect.left, y: boxRect.top - psRect.top }];
  stops.forEach((stop) => {
    const r = stop.querySelector(".marker").getBoundingClientRect();
    pts.push({ x: r.left - psRect.left, y: r.top - psRect.top });
  });

  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const prev = pts[i - 1];
    const curr = pts[i];
    const cx1 = prev.x + (curr.x - prev.x) * 0.5;
    const cy1 = prev.y;
    const cx2 = prev.x + (curr.x - prev.x) * 0.5;
    const cy2 = curr.y;
    d += ` C ${cx1},${cy1} ${cx2},${cy2} ${curr.x},${curr.y}`;
  }

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "rgba(24,0,58,0.15)");
  path.setAttribute("stroke-width", "2");
  path.setAttribute("stroke-dasharray", "8 6");
  svg.innerHTML = "";
  svg.appendChild(path);

  const len = path.getTotalLength();
  gsap.set(path, { strokeDasharray: len, strokeDashoffset: len });
  gsap.to(path, {
    strokeDashoffset: 0,
    ease: "none",
    scrollTrigger: {
      trigger: ".mstop.initial",
      start: "clamp(top center)",
      endTrigger: ".path-end",
      end: "clamp(top center)",
      scrub: 1
    }
  });
}

createMotionTimeline();
window.addEventListener("resize", createMotionTimeline);

gsap.utils.toArray(".text").forEach((el) => {
  gsap.to(el, {
    backgroundSize: "100% 100%",
    ease: "none",
    scrollTrigger: {
      trigger: el,
      start: "top 82%",
      end: "top 18%",
      scrub: true
    }
  });
});

ScrollTrigger.create({
  start: 0,
  end: "max",
  onUpdate: (self) => {
    document.body.style.filter = `hue-rotate(${Math.round(
      self.progress * 22
    )}deg)`;
  }
});

const isTouchDevice = () => window.matchMedia("(hover: none)").matches;

if (isTouchDevice()) {
  document.querySelectorAll(".text").forEach((el) => {
    el.addEventListener("click", () => {
      el.classList.toggle("tapped");
    });
  });
}
