/*** Simple transparent background with blur effect */

export default function BlurBackground() {
  return (
    <div className="fixed left-0 top-0 z-0 h-screen min-h-[100lvh] w-screen pointer-events-none scale-110 translate-x-[-5%] translate-y-[5%] backdrop-blur-[1px]" />
  );
}
