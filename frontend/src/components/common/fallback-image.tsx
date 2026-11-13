"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Image, { type ImageProps } from "next/image";

// FE-19: 외부 이미지(Community Dragon) 로드 실패 시 fallback으로 대체한다.
// 2026-11-13 CDragon 원본 서버 장애(캐시 우회 시 522) 때, 주소는 있는데
// 불러오지 못한 아이콘이 24px 상자 안에 alt 텍스트를 한 글자씩 세로로 쌓아
// 레이아웃을 밀어냈다 — 기존 코드는 주소가 null일 때만 폴백을 썼다.
// 이미지 주소는 브라우저가 CDragon에서 직접 받는다(next.config의 unoptimized).
export function FallbackImage({
  src,
  alt,
  fallback,
  ...imageProps
}: Omit<ImageProps, "src" | "onError"> & {
  src: string | null | undefined;
  fallback: ReactNode;
}) {
  // 실패한 주소를 기억해, 주소가 바뀌면 자동으로 다시 시도한다.
  const [failedSrc, setFailedSrc] = useState<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    // 서버 렌더링된 <img>가 하이드레이션 전에 이미 실패하면 React가 onError를
    // 전달하지 못한다. next/image는 src를 다시 넣어 재요청하지만 장애 시엔
    // 응답(522)까지 20초 가까이 걸려, 그동안 깨진 이미지가 보인다 — 마운트
    // 시점에 이미 실패한 이미지(complete인데 크기 0)는 바로 폴백으로 바꾼다.
    const img = imgRef.current;
    if (src && img && img.complete && img.naturalWidth === 0) {
      setFailedSrc(src);
    }
  }, [src]);

  if (!src || failedSrc === src) {
    return <>{fallback}</>;
  }

  return (
    <Image
      {...imageProps}
      ref={imgRef}
      src={src}
      alt={alt}
      onError={() => setFailedSrc(src)}
    />
  );
}
