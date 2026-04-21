/*** Simple transparent background with blur effect */

export default function BlurBackground() {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none scale-110 translate-x-[-5%] translate-y-[5%] backdrop-blur-[1px]" />
  );
}