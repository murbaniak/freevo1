#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>   
#include <time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <errno.h>
#include <signal.h>

#include "portable.h"
#include "readpng.h"
#include "osd.h"
#include "fs.h"
#include "fb.h"
#include "x11.h"


#define SCREEN_WIDTH 768
#define SCREEN_HEIGHT 576

#ifndef OSD_FB
#ifndef OSD_X11
#error Either OSD_FB or OSD_X11 must be defined!
#endif
#endif

#define TRANSP(t,col) ((t << 24) | col)

#define COL_RED     0xff0000
#define COL_GREEN   0x00ff00
#define COL_BLUE    0x0000ff
#define COL_BLACK   0x000000
#define COL_WHITE   0xffffff

#define ARRAY_LENGTH(a)  (sizeof(a)/sizeof(a[0]))

font_t *stdfont;

static uint8 framebuffer[SCREEN_HEIGHT][SCREEN_WIDTH][4]; /* BGR0 */

void osd_close (void);
void osd_update (void);
void osd_drawbitmap (char *filename, uint16 x0, uint16 y0);
void osd_drawline (int x0, int y0, int x1, int y1, int width, uint32 color);
void osd_drawbox (int x0, int y0, int x1, int y1, int width, uint32 color);
void osd_clearscreen (int color);
void osd_drawstring (font_t *pFont, char str[], int x, int y,
                     uint32 fgcol, uint32 bgcol, int *width);


void
parsecommand (char cmd[], char command[], char args[][1000], int *argc)
{
  char tmp[1000];
  int ctr = 0, tmpctr;
  int i;

  
  *argc = 0;

  /* Get the command */
  while ((cmd[ctr] != 0) && (cmd[ctr] != ';')) {
    command[ctr] = cmd[ctr];
    ctr++;
  }

  command[ctr] = 0;

  /* Step past the delimiter for additional args */
  if (cmd[ctr] != 0) ctr++;

  tmpctr = 0;
  while (cmd[ctr] != 0) {

    if (cmd[ctr] == ';') {
      tmp[tmpctr] = 0;
      strcpy (args[*argc], tmp);
      (*argc)++;
      tmpctr = 0;
      ctr++;
    }

    tmp[tmpctr++] = cmd[ctr++];
  }

  if (tmpctr) {
      tmp[tmpctr] = 0;
      strcpy (args[*argc], tmp);
      (*argc)++;
  }

  printf ("Got command '%s', args ", command);

  for (i = 0; i < *argc; i++) {
    printf ("arg%d = '%s' ", i+1, args[i]);
  }

  printf ("\n");
  
}


void
executecommand (char command[], char args[][1000], int argc)
{
  int tmp;

  
  if (!strcmp ("quit", command)) {
    printf ("Exec: quit\n");
    osd_close ();
    exit (0);
  }

  if (!strcmp ("clearscreen", command)) {
    printf ("Exec: clearscreen (0x%08x)\n", atoi (args[0]));
    osd_clearscreen (atoi (args[0]));
  }

  if (!strcmp ("setpixel", command)) {
    printf ("Exec: setpixel\n");
    osd_setpixel (atoi (args[0]), atoi (args[1]), atoi (args[2]));
  }

  if (!strcmp ("drawbitmap", command)) {
    printf ("Exec: drawbitmap\n");
    osd_drawbitmap (args[0], atoi (args[1]), atoi (args[2]));
  }

  if (!strcmp ("drawline", command)) {
    printf ("Exec: drawline\n");
    osd_drawline (atoi (args[0]), atoi (args[1]), atoi (args[2]),
                  atoi (args[3]), atoi (args[4]), atoi (args[5]));
  }

  if (!strcmp ("drawbox", command)) {
    printf ("Exec: drawbox\n");
    osd_drawbox (atoi (args[0]), atoi (args[1]), atoi (args[2]),
                 atoi (args[3]), atoi (args[4]), atoi (args[5]));
  }

  if (!strcmp ("drawstring", command)) {
    printf ("Exec: drawstring\n");
    osd_drawstring (stdfont, args[1], atoi (args[2]),
                    atoi (args[3]), atoi (args[4]), atoi (args[5]), &tmp);
  }
  
  if (!strcmp ("update", command)) {
     printf ("Exec: update\n");
     osd_update ();
  }
  
   
}


void
udpserver (int port)
{
  int rcv_fd;
  struct sockaddr_in rcv_addr;
  int rlen;
  struct sockaddr_in rx_addr;
  int rx_addr_len;
  uint8 buf[10000];
  char args[100][1000];
  int argc;
  char command[1000];
  int tmp;

  
  if ((rcv_fd = socket (AF_INET, SOCK_DGRAM, 0)) < 0) {
    perror ("could not create socket");
    exit (1);
  }
 
  memset (&rcv_addr, 0, sizeof (rcv_addr));
 
  rcv_addr.sin_family = PF_INET;
  rcv_addr.sin_port = htons (port);
  rcv_addr.sin_addr.s_addr = htonl (INADDR_ANY);
 
  if (bind (rcv_fd, (struct sockaddr *) &rcv_addr, sizeof (rcv_addr))) {
    perror ("*** bind error");
    exit (1);
  }

  osd_clearscreen (0x006d9bff);
  osd_drawstring (stdfont, "Waiting for client...",
                  300, 280, TRANSP(48, 0), TRANSP(255,0), &tmp);
  
  osd_update ();
  
  while (1) {
    printf ("Waiting for data...\n");
    
    if ((rlen = recvfrom (rcv_fd, buf, sizeof (buf), 0,
                          (struct sockaddr *) &rx_addr, &rx_addr_len)) > 0) {
      buf[rlen] = 0;
      printf ("Got command from client: '%s'\n", buf);
      parsecommand (buf, command, args, &argc);
      executecommand (command, args, argc);
      fflush (stdout);
    }
  }
  
      
}


void
osd_close (void)
{
#ifdef OSD_FB
   fb_close ();
#endif

#ifdef OSD_X11
   x11_close ();
#endif
}


void
osd_update (void)
{
#ifdef OSD_FB
    fb_update ((uint8 *) framebuffer);
#endif

#ifdef OSD_X11
    x11_update ((uint8 *) framebuffer);
#endif
}


/* Alpha blending algorithm. Uses fixedpoint math. */
#define ALPHA_BLEND(old, new, transp) (((old * transp) + (new*(255-transp))) >> 8)


void
osd_setpixel (uint16 x, uint16 y, uint32 color)
{
   uint8 old_r, old_g, old_b;
   uint8 r, g, b;
   uint8 new_r, new_g, new_b;
   uint8 t;
   

   /* Basic clipping */
  if ((x >= SCREEN_WIDTH) || (y >= SCREEN_HEIGHT)) {
    return;
  }
  
  t = color >> 24;

  if (t == 0x00) {              /* Straight copy */
     framebuffer[y][x][3] = 0;
     framebuffer[y][x][2] = (color >> 16) & 0xff;
     framebuffer[y][x][1] = (color >>  8) & 0xff;
     framebuffer[y][x][0] = (color >>  0) & 0xff;
  } else if (t < 255) {           /* Alpha blend */

     /* Current values */
     old_r = framebuffer[y][x][2];
     old_g = framebuffer[y][x][1];
     old_b = framebuffer[y][x][0];

     /* Incoming values */
     r = (color >> 16) & 0xff;
     g = (color >>  8) & 0xff;
     b = (color >>  0) & 0xff;

     /* Alpha blended values */
     new_r = ALPHA_BLEND (old_r, r, t);
     new_g = ALPHA_BLEND (old_g, g, t);
     new_b = ALPHA_BLEND (old_b, b, t);
     
     framebuffer[y][x][3] = 0;
     framebuffer[y][x][2] = new_r;
     framebuffer[y][x][1] = new_g;
     framebuffer[y][x][0] = new_b;
  } /* else don't change the pixel */
  
}


/* Draw a bitmap at the specified x0;y0. Only PNG for now... */
void
osd_drawbitmap (char *filename, uint16 x0, uint16 y0)
{
   uint32 *pBM;
   uint16 w, h;
   int x, y;
   
   
   if (read_png (filename, (uint8 **) &pBM, &w, &h) != OK) {
      fprintf (stderr, "cannot load bitmap '%s'!\n", filename);
      return;
   }

   for (y = 0; y < h; y++) {
      for (x = 0; x < w; x++) {
         osd_setpixel (x0 + x, y0 + y, *pBM++);
      }
   }

   free (pBM);
   
}


void
osd_drawline (int x0, int y0, int x1, int y1, int width, uint32 color)
{
  int tx0, tx1, ty0, ty1;
  int cx, cy;
  float32 m, fy, fx;
  int w;
  

  if (width == 0) width = 1;
  
  tx0 = x0; tx1 = x1;
  ty0 = y0; ty1 = y1;
  
  /* Check for horizontal line */
  if (y0 == y1) {
    if (x0 > x1) {
      tx0 = x1;
      tx1 = x0;
    }       
    
    for (cx = tx0; cx <= tx1; cx++) {
      for (w = 0; w < width; w++) {
        osd_setpixel (cx, y0+w, color);
      }
      
    }

    return;
  }

  /* Check for vertical line */
  if (x0 == x1) {
    if (y0 > y1) {
      ty0 = y1;
      ty1 = y0;
    }       
    
    for (cy = ty0; cy <= ty1; cy++) {
      for (w = 0; w < width; w++) {
        osd_setpixel (x0+w, cy, color);
      }
    }

    return;
  }

  /* General line */
  m = ((float32) (y1 - y0)) / ((float32) (x1 - x0));

  if (fabs (m) <= 1.0) {
    /* Move along the x-axis */
    if (x0 > x1) {
      tx0 = x1; tx1 = x0;
      ty0 = y1; ty1 = y0;
    }

    fy = ty0;
    for (cx = tx0; cx <= tx1; cx++) {
      for (w = 0; w < width; w++) {
        osd_setpixel (cx, (int) rint (fy) + w, color);
      }
      fy += m;
    }

    return;
  } else {
    /* Move along the y-axis */
    if (y0 > y1) {
      tx0 = x1; tx1 = x0;
      ty0 = y1; ty1 = y0;
    }
    
    fx = tx0;
    m = 1.0 / m;
    for (cy = ty0; cy <= ty1; cy++) {
      for (w = 0; w < width; w++) {
        osd_setpixel ((int) rint (fx) + w, cy, color);
      }
      fx += m;
    }

    return;
   
  }
  
}


void
osd_drawbox (int x0, int y0, int x1, int y1, int width, uint32 color)
{

   x0 -= width - 1;
   y0 -= width - 1;
   
   osd_drawline (x0, y0, x1, y0, width, color);
   osd_drawline (x1, y0, x1, y1 + width - 1, width, color);
   osd_drawline (x0, y0, x0, y1, width, color);
   osd_drawline (x0, y1, x1, y1, width, color);

}


void
osd_clearscreen (int color)
{
   uint32 *pBuf = (uint32 *) framebuffer;
   int i;


   /* Set the first line to the color in question */
   for (i = 0; i < SCREEN_WIDTH; i++) {
      pBuf[i] = color;
   }

   /* And then repeatedly copy that line to the other lines */
   for (i = 1; i < SCREEN_HEIGHT; i++) {
      memcpy (framebuffer[i], framebuffer[0], SCREEN_WIDTH*4);
   }

}


void
osd_drawstring (font_t *pFont, char str[], int x, int y,
            uint32 fgcol, uint32 bgcol, int *width)
{

   fs_puts (pFont, x, y, fgcol, bgcol, str);

   if (width != (int *) NULL) {
      *width = 0;
   }
   
}


static void doexit (int dummy1, siginfo_t *pInfo, void *pDummy)
{
   fprintf (stderr, "Got CTRL-C, exiting...\n");
   exit (0);
}


int
main (int ac, char *av[])
{
   char *fn;
   struct sigaction act;


   /* Set up signal action */
   act.sa_sigaction = doexit;
   sigfillset (&act.sa_mask);
   act.sa_flags = SA_SIGINFO;

   sigaction (SIGINT, &act, (struct sigaction *) NULL);

   if (ac < 2) {
      fn = (char *) NULL;
   } else {
      fn = av[1];
   }
   
#ifdef OSD_FB
   fb_open ();
#endif

#ifdef OSD_X11
   x11_open (SCREEN_WIDTH, SCREEN_HEIGHT);
#endif

   /* Try to open an the font module*/
   stdfont = fs_open (fn);      /* XXX use the name! */
   
   if (NULL == stdfont) {
      fprintf (stderr, "Couldnt open font\n");
      exit(1);
   }

#if 0
   {
      int i;


      osd_clearscreen (0);
      osd_drawline (0, 0, 100, 0, 5, COL_RED);
      osd_drawline (0, 20, 100, 20, 5, COL_GREEN);
      osd_drawline (0, 40, 100, 40, 5, COL_BLUE);
      osd_update ();
      getchar ();
   }  
#endif
  
   udpserver (16480);           /* XXX get config info from central file */
   
   osd_close ();
   
   exit (0);
  
}
