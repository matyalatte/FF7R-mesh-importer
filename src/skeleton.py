from io_util import *

class Bone:
    #name_id: id of name list
    #parent: parent bone's id
    #rot: quaternion
    #pos: position
    #size: size

    def __init__(self, f):
        self.name_id=read_uint32(f)
        self.instance = read_int32(f) #null?
        self.parent = read_int32(f)
    
    def read(f):
        return Bone(f)

    def read_pos(self, f):
        self.rot=read_float32_array(f, len=4)
        self.pos=read_vec3_f32(f)
        self.size=read_vec3_f32(f)

    def write(f, bone):
        write_uint32(f, bone.name_id)
        write_int32(f, bone.instance)
        write_int32(f, bone.parent)

    def write_pos(f, bone):
        write_float32_array(f, bone.rot)
        write_vec3_f32(f, bone.pos)
        write_vec3_f32(f, bone.size)

    def name(self, name):
        self.name=name

    def print_bones(bones, padding=2):
        pad=' '*padding
        i=0
        for b in bones:
            name=b.name
            parent_id = b.parent
            if parent_id<0:
                parent_name='None'
            else:
                parent_name=bones[parent_id].name
            print(pad+'id: '+str(i)+', name: '+name+', parent: '+parent_name)
            i+=1

    def name_bones(bones, name_list):
        for b in bones:
            id = b.name_id
            name = name_list[id]
            b.name(name)

    def get_bone_id(bones, bone_name):
        id=-1
        i=0
        for b in bones:
            if b.name==bone_name:
                id=i
                break
            i+=1
        return id

class Skeleton:
    #bones: bone data
    #bones2: there is more bone data. I don't known how it works.

    def __init__(self, f):
        self.offset=f.tell()
        self.bones = read_array(f, Bone.read)

        #read position
        bone_num=read_uint32(f)
        check(bone_num, len(self.bones), f, 'Parse failed! (Skeleton)')
        for b in self.bones:
            b.read_pos(f)

        self.name_to_index_map=read_array(f, Bone.read)

    def read(f):
        return Skeleton(f)

    def write(f, skeleton):
        write_array(f, skeleton.bones, Bone.write, with_length=True)
        write_array(f, skeleton.bones, Bone.write_pos, with_length=True)
        write_array(f, skeleton.name_to_index_map, Bone.write, with_length=True)

    def name_bones(self, name_list):
        Bone.name_bones(self.bones, name_list)

    def print(self, padding=0):
        pad=' '*padding
        print(pad+'Skeleton (offset: {})'.format(self.offset))
        print(pad+'  bone_num: {}'.format(len(self.bones)))
        Bone.print_bones(self.bones, padding=2+padding)