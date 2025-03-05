<script>

export default{
  props:{
    modelValue:{
      required: false,
      default: 0
    },
    min:{
      required: false,
      default: 0
    },
    max:{
      required: false,
      default: 100
    },
    disabled:{
      required: false,
      default: false
    },
    caster:{
      requierd: false,
      type: Function,
      default: (value)=>{return parseInt(value);}
    }
  },
  data(){
    return{
      dragging: false,
      valueStr: String(this.modelValue),
      maxWidth:900,
      startX: 0
    }
  },
  computed: {
    value:{
      get(){
        return this.modelValue;
      },
      set(val){
        this.$emit("update:modelValue", val);
      }
    }
  },
  methods:{
    handleDragStart(e){
      if(this.disabled) return;
      this.dragging = true;
      this.startX = e.clientX;
    },
    handleDrag(e){
      if(this.disabled) return;
      if(!this.dragging){
        return;
      }
      // if(e.target !== this.$refs.c_slider_main) return;
      e.preventDefault();
      e.stopPropagation();
      const aim = this.$refs.c_slider_main;
      if(aim) this.maxWidth = aim.offsetWidth - 10;

      let offsetX = e.clientX - this.startX;
      this.value += offsetX / this.maxWidth * (this.max - this.min);
      if(this.value > this.max){
        this.value = this.max;
      }
      if(this.value < this.min){
        this.value = this.min;
      }
      this.startX = e.clientX;
    },
    handleMouseWheel(e){
      if(e.deltaY > 0){
        this.value -= 1;
      }else if(e.deltaY < 0){
        this.value += 1;
      }
      if(this.value > this.max){
        this.value = this.max;
      }
      if(this.value < this.min){
        this.value = this.min;
      }
    },
    handleTouchStart(e){
      if(this.disabled) return;
      e.preventDefault();
      e.stopPropagation();
      this.startX = e.touches[0].clientX;
    },
    handleTouchMove(e){
      if(this.disabled) return;
      e.preventDefault();
      e.stopPropagation();
      const aim = this.$refs.c_slider_main;
      if(aim) this.maxWidth = aim.offsetWidth - 10;

      let moveX = e.touches[0].clientX - this.startX;
      this.value += moveX / this.maxWidth * (this.max - this.min) + this.min;
      if(this.value > this.max){
        this.value = this.max;
      }
      if(this.min >= this.value){
        this.value = this.min;
      }
      this.startX += moveX;
    },
    handleInputValue(e){
      let _val = e.target.value.replace(/[^\d]/g, "");
      if(!_val) {
        this.value = this.min;
        e.target.value = this.value;
        return;
      }
      this.value = parseInt(_val);
      if(this.value > this.max) this.value = this.max;
      if(this.value < this.min) this.value = this.min;
      e.target.value = this.value;
    },
    getMaxWidth(){
      const aim = this.$refs.c_slider_main;
      if(aim) this.maxWidth = aim.offsetWidth - 10;
    }
  },
  mounted() {
    this.getMaxWidth();
  }
}
</script>

<template>
<div class="c_slider">
  <input class="c_slider_value" :disabled="disabled" @input="handleInputValue" :value="caster(value)" />
  <div class="c_slider_main"
       @mousemove="handleDrag"
       @mousedown="handleDragStart"
       @mouseup="dragging=false"
       @mouseleave="dragging=false"
       @wheel="handleMouseWheel"
       @touchstart="handleTouchStart"
       @touchmove="handleTouchMove"
       :class="{disabled: disabled}"
       ref="c_slider_main"
  >
    <div class="c_slider_toggle"></div>
  </div>
</div>
</template>

<style scoped>
.c_slider{
  position: relative;
  padding: 5px;
  display: flex;
  flex-direction: row;
  align-items: center;
  width: 100%;
}

.c_slider_value{
  width: 40px;
  color: black;
  user-select: none;
  -webkit-user-select: none;
  outline:none;
  margin-right: 5px;
  background-color: white;
  border: 1px solid grey;
  border-radius: 2px;
}

.c_slider_main{
  position: relative;
  width: 100%;
  height: 20px;
  margin-right: 20px;
  cursor: pointer;
}

.c_slider_main.disabled{
  cursor: not-allowed;

  .c_slider_toggle{
    background-color: #d2d2d2;
  }
}

.c_slider_toggle{
  position: absolute;
  width: 16px;
  height: 16px;
  border: 1px solid grey;
  border-radius: 18px;
  box-shadow: 0 2px 3px black;
  background-color: white;
  top: 0;
  left: calc( v-bind("((value - min) / (max - min) * 100) + '%'") - 10px);
  overflow: hidden;
  z-index: 10;
}

.c_slider_main::before{
  content: "";
  display: block;
  height: 5px;
  width: v-bind("((value - min) / (max - min) * 100) + '%'");
  border: 1px solid grey;
  border-radius: 7px;
  background-color: rgb(25, 150, 62);
  position: absolute;
  top: calc(50% - 4px);
}

.c_slider_main::after{
  content: "";
  display: block;
  height: 5px;
  width: v-bind("((max - value) / (max - min) * 100) + '%'");
  border: 1px solid grey;
  border-radius: 7px;
  background-color: white;
  position: absolute;
  top: calc(50% - 4px);
  left: v-bind("((value - min) / (max - min) * 100) + '%'");
}
</style>
